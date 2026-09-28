# LearningDex

视频学习辅助桌面应用。以下命令均在 Windows PowerShell 的项目根目录执行。

## 从源码运行

准备 Python 3.9（当前验证版本，包含 Windows 的 `py` 启动器）和 Microsoft Edge WebView2 Runtime。仓库已包含构建好的前端资源，直接运行不需要 Node.js。

```powershell
py -3.9 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.main
```

如需解析新视频，启动后在设置中填写模型信息；也可复制 `personal.example.py` 为 `personal.py` 并填写。`personal.py` 已被 Git 忽略。

## 修改前端后重新构建

仅修改了 `app/web/` 的前端源码时需要 Node.js 和 npm：

```powershell
cd app/web
npm ci
npm run build
cd ../..
```

随后重新运行桌面程序。

## 从源码生成 Windows EXE

在已安装 `requirements.txt` 的虚拟环境中执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\tools\build_release.ps1
```

生成文件位于 `output/release/dist/LearningDex.exe`。构建脚本会检查所需资源，并排除个人配置及运行数据。

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
node --test tests/*.mjs
```

第二条命令需要 Node.js。
