# Playblast Native X 🎬

**Playblast Native X** is a highly robust, professional viewport animation capture (playblast) add-on designed specifically to overcome **Blender 5.0+** API constraints. It provides seamless frame-by-frame rendering with exact audio synchronization, custom warm-up delays for complex character rigs, and a failsafe settings recovery system.

---

## ✨ Key Features

* **Blender 5.0 API Lock Bypassing ("Engine Sandwich"):** Automatically bypasses Blender 5.0's strict format locks by safely transitioning `media_type` to `IMAGE` and formats to `PNG` in the background, preventing common `TypeError: enum "PNG" not found` API crashes.
* **Warm-up Time for Heavy Rigs:** Features a manual frame stepper with an adjustable pre-capture delay. Essential for complex facial setups, custom drivers, and heavy constraint rigs that require milliseconds to evaluate dependencies before capturing the viewport.
* **Frame-Accurate Audio Synchronization:** Automatically extracts scene audio (Mixdown) and intelligently offsets the stream via FFmpeg based on your custom timeline range, ensuring flawless lip-sync previewing regardless of where your playblast starts.
* **Active Viewport Targeting:** Intelligently detects your active 3D Viewport canvas, forcing the desired shading mode (`SOLID` or `MATERIAL`) exclusively for the playblast duration without breaking multi-viewport workflows.
* **ESC-Safe Failsafe Cleanup:** Integrated modal cancellation listeners ensure that if you press `ESC` or interrupt the render, your original interface settings, overlays, active render engine, and output paths are instantly restored.
* **Zero Disk Clutter:** Automatically purges all temporary frame sequences (`.png` files) immediately after encoding the final MP4 video.
* **Native Replay Integration:** Launches the final render instantly using Blender's high-speed standalone internal animation player (`blender -a`).

---

## 📥 Installation

1. Download the latest `__init__.py` file or package it into a `.zip`.
2. Open Blender and navigate to **Edit > Preferences > Add-ons**.
3. Click the drop-down menu in the top right and select **Install from Disk...**
4. Select the downloaded file/zip and enable the checkbox for **Render: Playblast Native X**.

---

## 🚀 Usage & Interface

Once enabled, a dedicated popover menu appears directly in the **3D Viewport Header** (next to the shading icons) for lightning-fast access.

### Popover Quick Controls:
* **Playblast:** Starts the sequence capture using your current scene timeline or active Preview Range.
* **Replay:** Instantly opens the generated `.mp4` file using Blender's standalone native player.
* **Open Folder:** Opens your operating system's file explorer directly to the active output destination.
* **Quick Toggles:** Instantly toggle **Include Audio**, **Stamp Metadata**, **Overlay Mode**, and **Shading Mode** without opening the main preferences window.

---

## ⚙️ Configuration

Access full parameters via **Edit > Preferences > Add-ons > Playblast Native X**:

| Setting | Description |
| :--- | :--- |
| **Folder Type** | Choose between saving inside the current `//` Project directory or a Custom absolute path. |
| **Subfolder** | Automatically nests outputs inside a designated clean sub-folder (default: `Playblast`). |
| **Shading Mode** | Override capture shading: **Solid** (Workbench), **Material** (EEVEE), or **Rendered** (Active Scene Engine). |
| **Resolution %** | Scale down the viewport capture resolution for faster execution. |
| **Warm-up (s)** | Delay time (in seconds) prior to capturing each frame to let character physics/drivers settle. |
| **Autoplay** | Automatically triggers the native replay window once FFmpeg finishes building the video. |

---

## ⚠️ Requirements

* **Blender 5.0** or higher.
* **FFmpeg:** Must be installed and accessible in your system's environment variables (`PATH`). If FFmpeg is missing, the add-on will report a `[WinError 2]` notification.

---

## 👨‍💻 Maintainer & License

Created and maintained by **mevluc**. 

Feel free to open issues, submit pull requests, or fork the repository to customize your studio's animation review pipeline!
