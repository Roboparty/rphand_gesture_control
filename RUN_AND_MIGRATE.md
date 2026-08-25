# 环境运行与笔记本迁移说明

## 当前电脑上的环境

项目目录：

```text
C:\gesture_hand_control_world_coords
```

已经创建本机虚拟环境：

```text
C:\gesture_hand_control_world_coords\.venv
```

当前验证过的主要版本：

- Python 3.12.13（64位）
- MediaPipe 0.10.14
- OpenCV 5.0.0
- NumPy 2.5.2

这些版本已经能够正常导入，并成功对 `diag_now.jpg` 运行 MediaPipe Hands。

## 当前电脑没有摄像头时

可以运行单张图片测试：

```powershell
Set-Location C:\gesture_hand_control_world_coords
.\.venv\Scripts\python.exe offline_image_test.py diag_now.jpg --output part1_diag_result.jpg
```

这个测试会打印：

- 是否检测到手；
- 左右手；
- 手势标签；
- 是否获得世界坐标；
- 五根手指弯曲度；
- 拇指侧摆值。

它不会连接真实灵巧手。

## 迁移到笔记本电脑

不要复制 `.venv`。Windows 虚拟环境保存了当前电脑的绝对路径，直接复制到另一台电脑通常不能可靠使用。

需要复制：

- 所有 `.py` 源文件；
- `config.yaml`；
- `requirements.txt`；
- `drivers/`；
- `vendor/`；
- `assets/`；
- 两份说明文档。

不需要复制：

- `.venv/`；
- `__pycache__/`；
- `build/` 和 `dist/`；
- 临时测试输出图片。

## 在笔记本上重新创建环境

先安装64位 Python 3.12，然后在 PowerShell 中执行：

```powershell
Set-Location <笔记本上的项目目录>
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

先用仿真驱动测试摄像头和连续映射：

```powershell
.\.venv\Scripts\python.exe main.py --driver sim --mode mirror --camera 0
```

如果摄像头0不可用，依次测试 `--camera 1`、`--camera 2`。

确认画面、21点骨架和弯曲度都正常之后，才连接USB-CANFD和灵巧手：

```powershell
.\.venv\Scripts\python.exe main.py --driver lhandpro --mode mirror --camera 0
```

第一次连接真机时，先按空格暂停指令发送，确认关节方向和零位安全后再恢复。
