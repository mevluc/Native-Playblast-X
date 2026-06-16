bl_info = {
    "name": "Playblast Native X",
    "author": "mevluc",
    "version": (3, 5),
    "blender": (5, 0, 0),
    "location": "View3D > Header",
    "description": "ESC Safe Playblast with automatic Media Type/Format switching, Warm-up, and precise audio sync.",
    "category": "Render",
}

import bpy
import os
import subprocess
import glob
import tempfile
import time
import re
import sys
import shutil
from bpy.types import Operator, Panel, AddonPreferences
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty, FloatProperty

# ------------------------------------------------------------------------
#   Addon Preferences
# ------------------------------------------------------------------------
class PLAYBLAST_X_Preferences(AddonPreferences):
    bl_idname = __name__

    folder_type: EnumProperty(
        name="Folder",
        items=[('PROJECT', "Project folder", ""), ('CUSTOM', "Custom folder", "")],
        default='PROJECT'
    )
    custom_folder: StringProperty(name="Custom Path", subtype='DIR_PATH', default="//")
    use_subfolder: BoolProperty(name="Subfolder", default=True)
    subfolder_name: StringProperty(name="", default="Playblast")
    
    shading_mode: EnumProperty(
        name="Shading Mode",
        items=[
            ('SOLID', "Solid (Workbench)", ""),
            ('MATERIAL', "Material (EEVEE)", ""),
            ('RENDERED', "Rendered (Active Engine)", ""),
        ],
        default='MATERIAL'
    )
    
    resolution_percentage: IntProperty(name="", default=50, min=1, max=100, subtype='PERCENTAGE')
    warmup_time: FloatProperty(name="Warm-up Time", default=0.1, min=0.0, max=5.0)
    include_audio: BoolProperty(name="Include Audio", default=False)
    stamp_metadata: BoolProperty(name="Stamp Metadata", default=True)
    
    overlays_type: EnumProperty(
        name="Overlays",
        items=[
            ('HIDE', "Hide all overlays", ""),
            ('KEEP', "Keep current overlays", ""),
        ],
        default='KEEP'
    )
    autoplay: BoolProperty(name="Autoplay", default=True)

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="OUTPUT", icon='FILE_FOLDER')
        col = box.column()
        col.prop(self, "folder_type")
        if self.folder_type == 'CUSTOM': col.prop(self, "custom_folder")
        row = col.row(); row.prop(self, "use_subfolder")
        if self.use_subfolder: row.prop(self, "subfolder_name")
        
        box = layout.box(); box.label(text="SETTINGS", icon='RENDER_ANIMATION')
        col = box.column()
        col.prop(self, "shading_mode", text="Shading")
        col.prop(self, "resolution_percentage", text="Resolution %")
        col.prop(self, "warmup_time", text="Warm-up (s)", icon='TIME')
        col.prop(self, "include_audio", text="Include Audio")
        col.prop(self, "stamp_metadata")
        col.prop(self, "overlays_type")
        col.prop(self, "autoplay")

# ------------------------------------------------------------------------
#   Operators
# ------------------------------------------------------------------------
class PLAYBLAST_X_OT_execute(Operator):
    """Media Type and Shading aware Playblast with Warm-up and ESC Safety"""
    bl_idname = "playblast_x.execute"
    bl_label = "Playblast"

    _timer = None
    _area = None
    _original_settings = {}
    _phase = 'SETUP'
    _start_frame = 0
    _end_frame = 0
    _current_frame = 0
    _last_time = 0.0
    _frames_dir = ""
    _base_dir = ""
    _file_name = ""

    def invoke(self, context, event):
        prefs = context.preferences.addons[__name__].preferences
        scene = context.scene
        rd = scene.render

        if scene.use_preview_range:
            self._start_frame = scene.frame_preview_start
            self._end_frame = scene.frame_preview_end
        else:
            self._start_frame = scene.frame_start
            self._end_frame = scene.frame_end

        if context.area and context.area.type == 'VIEW_3D':
            self._area = context.area
        else:
            self._area = next((a for a in context.screen.areas if a.type == 'VIEW_3D'), None)

        orig_overlay = self._area.spaces[0].overlay.show_overlays if self._area else True
        orig_shading = self._area.spaces[0].shading.type if self._area else 'SOLID'
        orig_media_type = getattr(rd.image_settings, "media_type", "IMAGE")
        
        self._original_settings = {
            'engine': rd.engine,
            'filepath': rd.filepath,
            'file_format': rd.image_settings.file_format,
            'media_type': orig_media_type, 
            'res_perc': rd.resolution_percentage,
            'use_stamp': rd.use_stamp,
            'render_display': context.preferences.view.render_display_type,
            'frame': scene.frame_current,
            'show_overlays': orig_overlay,
            'shading_type': orig_shading
        }

        self._base_dir = bpy.path.abspath("//") if prefs.folder_type == 'PROJECT' else bpy.path.abspath(prefs.custom_folder)
        if not self._base_dir: self._base_dir = tempfile.gettempdir()
        if prefs.use_subfolder: self._base_dir = os.path.join(self._base_dir, prefs.subfolder_name)
        os.makedirs(self._base_dir, exist_ok=True)

        self._file_name = bpy.path.display_name_from_filepath(bpy.data.filepath) or "playblast"
        self._frames_dir = os.path.join(tempfile.gettempdir(), f"pb_x_{int(time.time())}")
        os.makedirs(self._frames_dir, exist_ok=True)

        if prefs.shading_mode == 'SOLID': rd.engine = 'BLENDER_WORKBENCH'
        elif prefs.shading_mode == 'MATERIAL': rd.engine = 'BLENDER_EEVEE'
        
        if self._area:
            self._area.spaces[0].shading.type = prefs.shading_mode

        rd.resolution_percentage = prefs.resolution_percentage
        rd.use_stamp = prefs.stamp_metadata
        context.preferences.view.render_display_type = 'NONE'

        if self._area and prefs.overlays_type == 'HIDE':
            self._area.spaces[0].overlay.show_overlays = False
            self._area.tag_redraw()

        self._current_frame = self._start_frame
        self._phase = 'INIT_FORMAT'
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        prefs = context.preferences.addons[__name__].preferences
        scene = context.scene
        
        if event.type == 'ESC': 
            self.report({'INFO'}, "Playblast Cancelled by User")
            self.cleanup(context)
            return {'CANCELLED'}
        
        if event.type == 'TIMER':
            if self._phase == 'INIT_FORMAT':
                try:
                    if hasattr(scene.render.image_settings, "media_type"):
                        scene.render.image_settings.media_type = 'IMAGE'
                    scene.render.image_settings.file_format = 'PNG'
                except Exception as e:
                    print(f"Playblast Native X - Format validation: {e}")
                self._phase = 'STEP_FRAME'

            elif self._phase == 'STEP_FRAME':
                scene.frame_set(self._current_frame)
                context.view_layer.update()
                self._last_time = time.time()
                self._phase = 'WARMUP'
                
            elif self._phase == 'WARMUP':
                if (time.time() - self._last_time) >= prefs.warmup_time: self._phase = 'CAPTURE'
                
            elif self._phase == 'CAPTURE':
                scene.render.filepath = os.path.join(self._frames_dir, f"frame_{self._current_frame:04d}.png")
                bpy.ops.render.opengl(write_still=True, view_context=True)
                if self._current_frame >= self._end_frame: self._phase = 'FFMPEG'
                else: self._current_frame += 1; self._phase = 'STEP_FRAME'
                
            elif self._phase == 'FFMPEG':
                self.process_video(context)
                return {'FINISHED'}
                
        return {'PASS_THROUGH'}

    def process_video(self, context):
        prefs = context.preferences.addons[__name__].preferences
        scene = context.scene
        final_video = os.path.join(self._base_dir, self._file_name + ".mp4")
        fps = scene.render.fps / scene.render.fps_base
        
        # Videonun tam karesel süresini saniye olarak hesapla
        duration_frames = self._end_frame - self._start_frame + 1
        duration_sec = duration_frames / fps
        
        audio_file = None
        if prefs.include_audio:
            audio_path = os.path.join(self._frames_dir, "temp_audio.wav")
            bpy.ops.sound.mixdown(filepath=audio_path, container='WAV', codec='PCM')
            if os.path.exists(audio_path): audio_file = audio_path

        cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-start_number", str(self._start_frame), "-i", os.path.join(self._frames_dir, "frame_%04d.png")]
        
        if audio_file:
            # Ses dosyasının başlangıcı ile bizim renderın başlangıcı arasındaki fark
            offset_frames = self._start_frame - scene.frame_start
            offset_sec = max(0.0, offset_frames / fps)
            
            if offset_sec > 0:
                cmd.extend(["-ss", f"{offset_sec:.4f}"])
            
            cmd.extend(["-i", audio_file])
            
        cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18"])
        
        if audio_file:
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
            # -shortest parametresi risk yarattığı için kaldırıldı.
            
        # Çıktı videosunun süresini tam render alınan aralık kadar zorla (Donmaları ve kesilmeleri önler)
        cmd.extend(["-t", f"{duration_sec:.4f}"])
        cmd.append(final_video)
        
        try:
            si = None
            if os.name == 'nt':
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(cmd, startupinfo=si, check=True)
            self.report({'INFO'}, f"Saved: {final_video}")
            if prefs.autoplay: bpy.ops.playblast_x.replay()
        except Exception as e: self.report({'ERROR'}, f"FFmpeg: {e}")
        self.cleanup(context)

    def cancel(self, context):
        self.cleanup(context)

    def cleanup(self, context):
        if self._timer: 
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
            
        rd = context.scene.render
        if self._original_settings:
            rd.engine = 'BLENDER_WORKBENCH' 
            try:
                if hasattr(rd.image_settings, "media_type") and 'media_type' in self._original_settings:
                    rd.image_settings.media_type = self._original_settings['media_type']
                rd.image_settings.file_format = self._original_settings.get('file_format', rd.image_settings.file_format)
            except: pass
            
            rd.engine = self._original_settings.get('engine', rd.engine)
            rd.filepath = self._original_settings.get('filepath', rd.filepath)
            rd.resolution_percentage = self._original_settings.get('res_perc', rd.resolution_percentage)
            rd.use_stamp = self._original_settings.get('use_stamp', rd.use_stamp)
            context.preferences.view.render_display_type = self._original_settings.get('render_display', 'WINDOW')
            context.scene.frame_set(self._original_settings.get('frame', context.scene.frame_current))
            
            if self._area: 
                self._area.spaces[0].overlay.show_overlays = self._original_settings.get('show_overlays', True)
                if 'shading_type' in self._original_settings:
                    self._area.spaces[0].shading.type = self._original_settings['shading_type']
        
        if self._frames_dir and os.path.exists(self._frames_dir):
            try: shutil.rmtree(self._frames_dir)
            except: pass

class PLAYBLAST_X_OT_replay(Operator):
    bl_idname = "playblast_x.replay"; bl_label = "Replay"
    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        path = bpy.path.abspath("//") if prefs.folder_type == 'PROJECT' else bpy.path.abspath(prefs.custom_folder)
        if prefs.use_subfolder: path = os.path.join(path, prefs.subfolder_name)
        file = os.path.join(path, (bpy.path.display_name_from_filepath(bpy.data.filepath) or "playblast") + ".mp4")
        if os.path.exists(file): subprocess.Popen([bpy.app.binary_path, "-a", file])
        return {'FINISHED'}

class PLAYBLAST_X_OT_open_settings(Operator):
    bl_idname = "playblast_x.open_settings"; bl_label = "Settings"
    def execute(self, context):
        bpy.ops.screen.userpref_show(); context.preferences.active_section = 'ADDONS'
        try: bpy.data.window_managers["WinMan"].addon_search = "Playblast Native X"
        except: pass
        return {'FINISHED'}

class PLAYBLAST_X_OT_open_folder(Operator):
    bl_idname = "playblast_x.open_folder"; bl_label = "Open Folder"
    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        path = bpy.path.abspath("//") if prefs.folder_type == 'PROJECT' else bpy.path.abspath(prefs.custom_folder)
        if prefs.use_subfolder: path = os.path.join(path, prefs.subfolder_name)
        if os.path.exists(path): bpy.ops.wm.path_open(filepath=path)
        return {'FINISHED'}

class VIEW3D_PT_playblast_x_popover(Panel):
    bl_space_type = 'VIEW_3D'; bl_region_type = 'HEADER'; bl_label = ""
    def draw(self, context):
        layout = self.layout; layout.scale_y = 1.2
        layout.operator("playblast_x.execute", text="Playblast", icon='RENDER_ANIMATION')
        layout.scale_y = 1.0; row = layout.row(align=True)
        row.operator("playblast_x.replay", text="Replay", icon='PLAY')
        row.operator("playblast_x.open_folder", text="Open Folder", icon='FILE_FOLDER')
        
        prefs = context.preferences.addons[__name__].preferences
        col = layout.column(align=True)
        col.prop(prefs, "include_audio", text="Include Audio")
        col.prop(prefs, "stamp_metadata", text="Stamp Metadata")
        
        layout.prop(prefs, "overlays_type", text="")
        layout.prop(prefs, "shading_mode", text="")
        layout.operator("playblast_x.open_settings", text="More Settings...", icon='PREFERENCES')

def draw_button(self, context): self.layout.popover("VIEW3D_PT_playblast_x_popover", text="", icon='RENDER_ANIMATION')

classes = (PLAYBLAST_X_Preferences, PLAYBLAST_X_OT_execute, PLAYBLAST_X_OT_replay, PLAYBLAST_X_OT_open_folder, PLAYBLAST_X_OT_open_settings, VIEW3D_PT_playblast_x_popover)

def register():
    for cls in classes: bpy.utils.register_class(cls)
    bpy.types.VIEW3D_HT_header.append(draw_button)

def unregister():
    bpy.types.VIEW3D_HT_header.remove(draw_button)
    for cls in reversed(classes): bpy.utils.unregister_class(cls)

if __name__ == "__main__": register()
