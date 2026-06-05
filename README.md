# PDF Watermark Remover

一个本地运行的 PDF 去水印桌面工具，用于处理用户有权处理的 PDF 文件。
项目优先采用对象级去水印方式，尽量保留 PDF 的文字可选中、页面结构、链接、页数和页面尺寸。

> 仅用于处理你拥有合法权限的 PDF。
> 本项目不提供 DRM 绕过、密码破解、权限规避或未授权文档处理能力。

## 功能特性

- 本地处理，不上传云端
- Windows 桌面应用
- 自动检测 PDF 水印候选
- 支持候选确认
- 支持处理前后预览
- 支持选择导出路径
- 导出后可直接打开生成的 PDF 或打开所在文件夹
- 导出后进行结构验证：
  - 删除数量检查
  - 页数一致性检查
  - 页面尺寸一致性检查
  - 链接数量一致性检查
  - 正文文本一致性检查
- 当前支持的对象级水印类型：
  - 重复浅色文本水印
  - PDF Watermark Artifact
  - 部分图片 XObject 水印

## 下载与运行

当前 Windows portable 版本位于：

```text
release-latest/PDF Watermark Remover 0.1.0.exe
```

下载仓库后，可直接运行该 exe 文件。

> 如果通过 GitHub 下载源码压缩包，Git LFS 文件可能不会自动包含完整 exe。
> 建议使用 `git clone` 并确保已安装 Git LFS。

```bash
git clone https://github.com/chenchencc47/pdf-watermark-remover.git
cd pdf-watermark-remover
git lfs pull
```

## 使用方式

1. 启动 `PDF Watermark Remover 0.1.0.exe`
2. 点击“选择 PDF”
3. 等待工具自动检测水印候选
4. 根据检测结果选择需要删除的候选
5. 点击“生成预览”查看处理前后效果
6. 点击“导出去水印 PDF”
7. 选择输出路径
8. 导出完成后，可点击“打开文件”或“打开所在文件夹”

## 技术栈

桌面端：

- Electron
- React
- TypeScript
- Vite

PDF 处理引擎：

- Python
- PyMuPDF
- PyInstaller

测试：

- Vitest
- Testing Library
- pytest

## 项目结构

```text
pdf-watermark-remover/
├── engine/                     # Python PDF 处理引擎
│   ├── pdf_watermark_remover/
│   │   ├── cli.py              # Python CLI 入口
│   │   ├── content_units.py    # PDF 内容流 unit 抽取
│   │   ├── detect.py           # 水印候选检测
│   │   ├── remove.py           # 对象级删除
│   │   ├── verify_export.py    # 导出结果验证
│   │   └── ...
│   └── tests/                  # Python 引擎测试
├── src/
│   ├── main/                   # Electron main process
│   ├── preload/                # Electron preload API
│   ├── renderer/               # React UI
│   └── shared/                 # 前后端共享类型
├── release-latest/             # 最新 Windows portable exe
├── package.json
└── README.md
```

## 本地开发

安装依赖：

```bash
npm install
```

启动开发环境：

```bash
npm run dev
```

运行 renderer 测试：

```bash
npm run test:renderer
```

运行 Python engine 测试：

```bash
PYTHONPATH=engine ../.pdf-inspect-venv/Scripts/python.exe -m pytest engine/tests -q
```

构建前端和 Electron 代码：

```bash
npm run build
```

打包 Python 引擎：

```bash
npm run build:engine
```

生成 Windows portable exe：

```bash
npx electron-builder --win portable --config.directories.output=release-latest
```

如果默认 `release/` 目录里的旧文件被系统或杀毒软件锁住，可以继续使用 `release-latest/` 作为输出目录。

## 当前能力边界

当前版本优先处理 PDF 内部仍保留独立对象的水印，例如：

- 可识别的文本对象水印
- 标记为 `/Subtype /Watermark` 的 Artifact
- 部分可安全定位的图片 XObject

暂不保证处理：

- 扫描件中已经烙进整页图片的水印
- 与正文图像混合在一起的复杂水印
- 需要 DRM 绕过或密码破解的 PDF
- 无法安全区分正文和水印的对象

## 安全与合规说明

本项目只面向合法、授权的 PDF 处理场景，例如：

- 处理自己制作的 PDF
- 处理拥有编辑或再加工权限的资料
- 移除自己或机构添加的水印
- 学习 PDF 对象结构与本地文档处理技术

请勿将本工具用于未授权内容、版权规避、DRM 绕过或任何违法用途。

## License

MIT License. See [LICENSE](LICENSE) for details.
