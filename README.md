# 🔗 Odoo 模块依赖分析器

一个强大的Odoo模块依赖关系分析工具，支持扫描、分析、可视化模块依赖关系。

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ 功能特性

### 基础功能
- 🔍 **模块扫描** - 自动扫描目录下的所有Odoo模块
- 📊 **依赖分析** - 解析模块间的依赖关系
- 🌐 **Web可视化** - 交互式依赖关系图
- 🌳 **依赖树** - 展示模块的依赖层级
- 🔄 **循环检测** - 检测循环依赖问题
- ❓ **缺失检测** - 发现缺失的依赖模块
- 📋 **安装顺序** - 计算正确的模块安装顺序

### 升级分析（高级功能）
- 🗄️ **模型分析** - 解析数据模型定义、字段和关系
- ⚡ **影响评估** - 评估升级模块的影响范围和风险
- 🔄 **版本对比** - 对比两个版本的模块差异

### 便捷操作
- 📂 **文件夹浏览器** - 可视化选择本地路径
- 📜 **历史记录** - 自动保存扫描过的路径
- ⚡ **快速选择** - 一键选择常用路径

## 🚀 快速开始

### 本地运行

```bash
# 克隆项目
git clone https://github.com/your-username/odoo-depends.git
cd odoo-depends

# 安装依赖
pip install -r requirements.txt

# 启动Web服务
python run.py -p 8080

# 访问 http://localhost:8080
```

### 命令行使用

```bash
# 安装工具
pip install -e .

# 扫描模块
odoo-depends scan /path/to/odoo/addons

# 查看模块依赖
odoo-depends deps /path/to/odoo/addons sale

# 生成依赖图
odoo-depends graph /path/to/odoo/addons -o deps.html

# 检查问题
odoo-depends check /path/to/odoo/addons

# 启动Web服务
odoo-depends serve -p 8080
```

## 📖 Web界面功能

| 菜单 | 功能 |
|------|------|
| 📂 扫描模块 | 配置路径并扫描Odoo模块 |
| 📊 依赖图 | 交互式可视化依赖关系 |
| 📋 模块列表 | 查看所有模块详情 |
| 🌳 依赖树 | 展示依赖层级结构 |
| 📦 安装顺序 | 计算正确的安装顺序 |
| 🔍 问题检查 | 检测循环依赖和缺失 |
| 🗄️ 模型分析 | 解析数据模型定义 |
| ⚡ 影响评估 | 评估升级风险 |
| 🔄 版本对比 | 对比版本差异 |

## 🎨 可视化说明

### 节点颜色

| 颜色 | 含义 |
|------|------|
| 🔴 红色 | 应用模块 (Application) |
| 🔵 蓝色 | 核心模块 (Core) |
| 🟢 绿色 | 普通模块 (Normal) |
| ⚪ 灰色 | 外部依赖 (External) |

## 📁 项目结构

```
odoo-depends/
├── odoo_depends/
│   ├── __init__.py          # 包初始化
│   ├── analyzer.py          # 核心分析器
│   ├── upgrade_analyzer.py  # 升级分析器
│   ├── visualizer.py        # 可视化模块
│   ├── web_app.py           # Flask Web应用
│   └── cli.py               # 命令行接口
├── odoo-test/
│   └── addons/              # 示例模块
├── requirements.txt         # 依赖列表
├── run.py                   # 快速启动脚本
├── setup.py                 # 安装脚本
└── README.md                # 项目说明
```

## 🛠️ 技术栈

- **Python 3.9+**
- **Flask** - Web框架
- **NetworkX** - 图计算库
- **PyVis** - 交互式可视化
- **Click** - 命令行框架

## 🚀 部署到 Vercel

### 方式一：通过 Vercel Dashboard（推荐）

1. 访问 [vercel.com](https://vercel.com) 并登录
2. 点击 "Add New Project"
3. 导入 GitHub 仓库 `odoo-depends`
4. 使用默认配置，点击 "Deploy"

### 方式二：通过命令行

```bash
# 登录 Vercel
npx vercel login

# 部署
npx vercel --prod
```

## 📝 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 🔗 链接

- **GitHub**: https://github.com/Albertsun6/odoo-depends
