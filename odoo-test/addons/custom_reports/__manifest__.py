# -*- coding: utf-8 -*-
{
    'name': '自定义报表模块',
    'version': '17.0.1.0.0',
    'category': 'Reporting',
    'summary': '综合报表和数据分析',
    'description': """
        自定义报表模块，整合所有模块的数据分析。
        
        功能：
        - 销售报表
        - 采购报表  
        - 库存报表
        - 综合分析
    """,
    'author': 'Galaxy',
    'website': 'https://example.com',
    'depends': ['custom_sale', 'custom_purchase', 'custom_inventory', 'account'],
    'data': [],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
