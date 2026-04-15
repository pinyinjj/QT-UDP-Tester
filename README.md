# QT-UDP-Tester

A high-performance UDP debugging and protocol testing tool based on PyQt5 and Fluent Design.

[**简体中文 (Chinese Version)**](docs/README_zh.md)

![Main Interface](docs/mainframe.png)

## 🚀 Key Features

### 1. Protocol Management & Persistence
* **Database Driven**: Uses SQLite local database to store protocol configurations, supporting rapid retrieval of numerous protocols.

![Protocol Edit](docs/database.png)

* **Flexible Configuration**: Independently configure name, target/listening port, payload, and loop frequency (0.01Hz - 1000Hz) for each protocol.
* **Type Isolation**: Separate "Send" and "Receive" types to simplify operations in complex testing scenarios.

### 2. High-Performance Communication Engine
* **Asynchronous Concurrency**: Based on `select` multiplexing and multi-threading to ensure UI remains smooth under high-frequency packet impact.
* **Data Batching**: Built-in packet buffer with an intelligent merge-refresh mechanism to balance real-time performance and system overhead.
* **Precise Timing**: High-precision timers ensure minimal interval error for loop sending tasks.

### 3. Modern Interaction Experience
* **Fluent Design Visuals**: Perfectly adapted to Windows 11 visual style, supporting Dark/Light themes.
* **Real-time Monitoring**: Structured display of packet sources, microsecond-level timestamps, local ports, and raw content.
* **Dynamic View Adjustment**:
    * **Font Zooming**: Supports real-time `Add/Remove` zooming for table and log areas to reduce long-term observation fatigue.
    * **Elastic Layout**: Built-in view resizer to freely allocate display space between monitoring and configuration areas.
* **Smart Filtering**: Supports real-time multi-dimensional filtering of received data streams via Tags.

## 🛠️ Installation Requirements

* **Python**: 3.8 or higher
* **OS**: Windows / Linux / macOS

### Install Dependencies
```bash
pip install -r requirements.txt
```

## 📖 Usage Guide

1. **Run Application**:
   ```bash
   python udp_tool_gui.py
   ```
2. **Define Protocol**: Click the "Add" button and enter protocol parameters in the Fluent-style dialog.

![Save Configuration](docs/save.png)

3. **Data Interaction**:
   - Protocols configured as `Send` can be triggered manually or automatically via loop.
   - Protocols configured as `Receive` will automatically start listening on local ports.
4. **View Adjustment**: Use the zoom buttons in the top right of the monitoring table to adjust fonts; drag the middle divider to adjust view proportions.

## 📂 Project Structure
* `udp_tool_gui.py`: Main program logic and GUI implementation.
* `icons/`: UI resource files.
* `requirements.txt`: Dependency list.
* `~/.qt-udp-tester/`: Default storage path for config files and protocol database.

---
*Professional, Fast, and Fluent.*
