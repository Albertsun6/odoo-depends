"""
命令行接口 - 使用Click框架
"""

import sys
import json
from pathlib import Path
from typing import List, Optional
import click

from .analyzer import OdooModuleAnalyzer
from .visualizer import DependencyVisualizer


# 颜色配置
class Colors:
    RED = 'red'
    GREEN = 'green'
    BLUE = 'cyan'
    YELLOW = 'yellow'
    MAGENTA = 'magenta'


def print_banner():
    """打印工具横幅"""
    banner = r"""
    ╔═══════════════════════════════════════════════════════════╗
    ║   ___      _             ____                          _  ║
    ║  / _ \  __| | ___   ___ |  _ \  ___ _ __   ___ _ __   __| |║
    ║ | | | |/ _` |/ _ \ / _ \| | | |/ _ \ '_ \ / _ \ '_ \ / _` |║
    ║ | |_| | (_| | (_) | (_) | |_| |  __/ |_) |  __/ | | | (_| |║
    ║  \___/ \__,_|\___/ \___/|____/ \___| .__/ \___|_| |_|\__,_|║
    ║                                    |_|                    ║
    ║                                                           ║
    ║            🔗 Odoo 模块依赖分析器 v1.0.0                   ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    click.echo(click.style(banner, fg=Colors.BLUE))


@click.group()
@click.version_option(version='1.0.0', prog_name='odoo-depends')
def cli():
    """Odoo 模块依赖分析器 - 分析、可视化Odoo模块依赖关系"""
    pass


@cli.command()
@click.argument('paths', nargs=-1, required=True, type=click.Path(exists=True))
@click.option('--output', '-o', default=None, help='输出JSON文件路径')
@click.option('--quiet', '-q', is_flag=True, help='静默模式，只输出结果')
def scan(paths: tuple, output: Optional[str], quiet: bool):
    """扫描指定路径下的所有Odoo模块
    
    PATHS: 一个或多个Odoo模块目录路径
    
    示例:
        odoo-depends scan /opt/odoo/addons
        odoo-depends scan /opt/odoo/addons /opt/custom-addons -o result.json
    """
    if not quiet:
        print_banner()
        click.echo(click.style("\n📂 开始扫描模块...\n", fg=Colors.YELLOW))
    
    analyzer = OdooModuleAnalyzer(list(paths))
    modules = analyzer.scan_modules()
    
    if not modules:
        click.echo(click.style("❌ 未找到任何Odoo模块", fg=Colors.RED))
        sys.exit(1)
    
    analyzer.build_dependency_graph()
    stats = analyzer.get_statistics()
    
    if not quiet:
        # 打印扫描结果
        click.echo(click.style(f"✅ 成功扫描 {len(modules)} 个模块\n", fg=Colors.GREEN))
        
        # 打印统计信息
        click.echo(click.style("📊 统计信息:", fg=Colors.BLUE, bold=True))
        click.echo(f"  • 模块总数: {stats['total_modules']}")
        click.echo(f"  • 依赖关系: {stats['total_dependencies']}")
        click.echo(f"  • 应用模块: {len(stats['applications'])}")
        click.echo(f"  • 模块分类: {len(stats['categories'])}")
        
        if stats['circular_dependencies']:
            click.echo(click.style(f"\n⚠️  循环依赖: {len(stats['circular_dependencies'])}", fg=Colors.YELLOW))
            for cycle in stats['circular_dependencies']:
                click.echo(f"    {' → '.join(cycle)}")
        
        if stats['missing_dependencies']:
            click.echo(click.style(f"\n❓ 缺失依赖:", fg=Colors.YELLOW))
            for mod, deps in stats['missing_dependencies'].items():
                click.echo(f"    {mod}: {', '.join(deps)}")
        
        click.echo()
        
        # 打印模块列表
        click.echo(click.style("📦 模块列表:", fg=Colors.BLUE, bold=True))
        for name, module in sorted(modules.items()):
            app_badge = click.style(" [应用]", fg=Colors.RED) if module.application else ""
            deps_count = len(module.depends)
            click.echo(f"  • {click.style(name, fg=Colors.GREEN)}{app_badge} (v{module.version}, {deps_count}个依赖)")
    
    # 输出JSON
    if output:
        analyzer.export_to_json(output)
        if not quiet:
            click.echo(click.style(f"\n💾 结果已保存至: {output}", fg=Colors.GREEN))
    elif quiet:
        # 静默模式下输出JSON到标准输出
        data = {
            'modules': {name: mod.to_dict() for name, mod in modules.items()},
            'statistics': stats
        }
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))


@cli.command()
@click.argument('paths', nargs=-1, required=True, type=click.Path(exists=True))
@click.argument('module_name')
@click.option('--include-core/--no-core', default=True, help='是否包含核心模块')
@click.option('--depth', '-d', default=5, help='显示深度')
def deps(paths: tuple, module_name: str, include_core: bool, depth: int):
    """查看指定模块的依赖关系
    
    PATHS: Odoo模块目录路径
    MODULE_NAME: 要分析的模块名
    
    示例:
        odoo-depends deps /opt/odoo/addons sale
        odoo-depends deps /opt/odoo/addons sale --no-core
    """
    print_banner()
    
    analyzer = OdooModuleAnalyzer(list(paths))
    analyzer.scan_modules()
    analyzer.build_dependency_graph()
    
    if module_name not in analyzer.modules:
        click.echo(click.style(f"❌ 未找到模块: {module_name}", fg=Colors.RED))
        sys.exit(1)
    
    module = analyzer.modules[module_name]
    all_deps = analyzer.get_all_dependencies(module_name, include_core)
    reverse_deps = analyzer.get_reverse_dependencies(module_name)
    dep_depth = analyzer.get_dependency_depth(module_name)
    
    click.echo(click.style(f"\n📦 模块: {module_name}", fg=Colors.BLUE, bold=True))
    click.echo(f"  版本: {module.version}")
    click.echo(f"  分类: {module.category or '无'}")
    click.echo(f"  作者: {module.author or '无'}")
    click.echo(f"  应用: {'是' if module.application else '否'}")
    click.echo(f"  依赖深度: {dep_depth}")
    
    click.echo(click.style(f"\n🔗 直接依赖 ({len(module.depends)}):", fg=Colors.BLUE))
    for dep in sorted(module.depends):
        is_core = dep in analyzer.CORE_MODULES
        color = Colors.BLUE if is_core else Colors.GREEN
        badge = " [核心]" if is_core else ""
        click.echo(f"  • {click.style(dep, fg=color)}{badge}")
    
    click.echo(click.style(f"\n📊 所有依赖 ({len(all_deps)}):", fg=Colors.BLUE))
    for dep in sorted(all_deps):
        is_core = dep in analyzer.CORE_MODULES
        color = Colors.BLUE if is_core else Colors.GREEN
        click.echo(f"  • {click.style(dep, fg=color)}")
    
    click.echo(click.style(f"\n🔄 被依赖 ({len(reverse_deps)}):", fg=Colors.BLUE))
    for dep in sorted(reverse_deps):
        click.echo(f"  • {click.style(dep, fg=Colors.MAGENTA)}")
    
    # 显示依赖树
    click.echo(click.style(f"\n🌳 依赖树:", fg=Colors.BLUE, bold=True))
    visualizer = DependencyVisualizer(analyzer)
    tree = visualizer.generate_module_tree(module_name, depth)
    click.echo(tree)


@cli.command()
@click.argument('paths', nargs=-1, required=True, type=click.Path(exists=True))
@click.option('--modules', '-m', multiple=True, help='只包含指定模块（可多次使用）')
def order(paths: tuple, modules: tuple):
    """获取模块安装顺序
    
    PATHS: Odoo模块目录路径
    
    示例:
        odoo-depends order /opt/odoo/addons
        odoo-depends order /opt/odoo/addons -m sale -m purchase
    """
    print_banner()
    
    analyzer = OdooModuleAnalyzer(list(paths))
    analyzer.scan_modules()
    analyzer.build_dependency_graph()
    
    module_list = list(modules) if modules else None
    install_order = analyzer.get_install_order(module_list)
    
    if not install_order:
        click.echo(click.style("❌ 无法确定安装顺序（可能存在循环依赖）", fg=Colors.RED))
        sys.exit(1)
    
    click.echo(click.style("\n📋 安装顺序:", fg=Colors.BLUE, bold=True))
    for i, mod in enumerate(install_order, 1):
        is_core = mod in analyzer.CORE_MODULES
        color = Colors.BLUE if is_core else Colors.GREEN
        click.echo(f"  {i:3}. {click.style(mod, fg=color)}")


@cli.command()
@click.argument('paths', nargs=-1, required=True, type=click.Path(exists=True))
@click.option('--output', '-o', default='dependency_graph.html', help='输出HTML文件路径')
@click.option('--exclude-external', '-e', is_flag=True, help='排除外部依赖')
@click.option('--modules', '-m', multiple=True, help='只包含指定模块')
@click.option('--open', '-O', 'open_browser', is_flag=True, default=True, help='生成后自动打开浏览器（默认开启）')
@click.option('--no-open', is_flag=True, help='不自动打开浏览器')
def graph(paths: tuple, output: str, exclude_external: bool, modules: tuple, open_browser: bool, no_open: bool):
    """生成交互式依赖图并在浏览器中打开
    
    PATHS: Odoo模块目录路径
    
    示例:
        odoo-depends graph /opt/odoo/addons
        odoo-depends graph /opt/odoo/addons -o deps.html --no-open
        odoo-depends graph /opt/odoo/addons -e -m sale -m purchase
    """
    import webbrowser
    from pathlib import Path
    
    print_banner()
    
    click.echo(click.style("\n🔄 正在扫描模块...", fg=Colors.YELLOW))
    
    analyzer = OdooModuleAnalyzer(list(paths))
    modules_found = analyzer.scan_modules()
    analyzer.build_dependency_graph()
    
    click.echo(click.style(f"✅ 扫描完成: {len(modules_found)} 个模块", fg=Colors.GREEN))
    click.echo(click.style("\n🔄 正在生成依赖图...", fg=Colors.YELLOW))
    
    visualizer = DependencyVisualizer(analyzer)
    
    filter_modules = list(modules) if modules else None
    
    output_path = visualizer.generate_interactive_html(
        output,
        filter_modules=filter_modules,
        include_external=not exclude_external,
    )
    
    # 获取绝对路径
    abs_path = str(Path(output_path).resolve())
    
    click.echo(click.style(f"\n✅ 依赖图已生成: {abs_path}", fg=Colors.GREEN))
    
    # 自动打开浏览器（除非指定--no-open）
    if open_browser and not no_open:
        click.echo(click.style("🌐 正在打开浏览器...", fg=Colors.BLUE))
        webbrowser.open(f'file://{abs_path}')


@cli.command()
@click.argument('paths', nargs=-1, required=True, type=click.Path(exists=True))
@click.option('--format', '-f', type=click.Choice(['json', 'dot']), default='json', help='导出格式')
@click.option('--output', '-o', required=True, help='输出文件路径')
def export(paths: tuple, format: str, output: str):
    """导出分析结果
    
    PATHS: Odoo模块目录路径
    
    示例:
        odoo-depends export /opt/odoo/addons -f json -o result.json
        odoo-depends export /opt/odoo/addons -f dot -o graph.dot
    """
    print_banner()
    
    analyzer = OdooModuleAnalyzer(list(paths))
    analyzer.scan_modules()
    analyzer.build_dependency_graph()
    
    if format == 'json':
        analyzer.export_to_json(output)
    elif format == 'dot':
        analyzer.export_to_dot(output)
    
    click.echo(click.style(f"\n✅ 已导出至: {output}", fg=Colors.GREEN))


@cli.command()
@click.option('--host', '-h', default='0.0.0.0', help='监听地址')
@click.option('--port', '-p', default=5000, help='监听端口')
@click.option('--debug', '-d', is_flag=True, help='调试模式')
def serve(host: str, port: int, debug: bool):
    """启动Web服务器
    
    示例:
        odoo-depends serve
        odoo-depends serve -p 8080
        odoo-depends serve --debug
    """
    print_banner()
    
    from .web_app import run_server
    run_server(host=host, port=port, debug=debug)


@cli.command()
@click.argument('paths', nargs=-1, required=True, type=click.Path(exists=True))
def check(paths: tuple):
    """检查模块问题（循环依赖、缺失依赖等）
    
    PATHS: Odoo模块目录路径
    
    示例:
        odoo-depends check /opt/odoo/addons
    """
    print_banner()
    
    analyzer = OdooModuleAnalyzer(list(paths))
    analyzer.scan_modules()
    analyzer.build_dependency_graph()
    
    issues_found = False
    
    # 检查循环依赖
    cycles = analyzer.find_circular_dependencies()
    if cycles:
        issues_found = True
        click.echo(click.style(f"\n🔄 循环依赖 ({len(cycles)}):", fg=Colors.RED, bold=True))
        for cycle in cycles:
            click.echo(f"   {' → '.join(cycle)} → {cycle[0]}")
    
    # 检查缺失依赖
    missing = analyzer.find_missing_dependencies()
    if missing:
        issues_found = True
        click.echo(click.style(f"\n❓ 缺失依赖:", fg=Colors.YELLOW, bold=True))
        for mod, deps in missing.items():
            click.echo(f"   {click.style(mod, fg=Colors.GREEN)}: {', '.join(deps)}")
    
    # 检查不可安装模块
    not_installable = [m for m in analyzer.modules.values() if not m.installable]
    if not_installable:
        click.echo(click.style(f"\n⚠️  不可安装模块 ({len(not_installable)}):", fg=Colors.YELLOW, bold=True))
        for mod in not_installable:
            click.echo(f"   • {mod.name}")
    
    if not issues_found:
        click.echo(click.style("\n✅ 未发现问题!", fg=Colors.GREEN, bold=True))
    else:
        click.echo()


def main():
    """主入口"""
    cli()


if __name__ == '__main__':
    main()
