from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QFont, QKeySequence
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QListWidget, QPushButton, QTabWidget, QTextEdit, QToolBar, QVBoxLayout, QWidget


def build_flow_sidebar(window, button_style):
    window.flow_sidebar = QFrame()
    window.flow_sidebar.setFixedWidth(260)
    flow_sidebar_layout = QVBoxLayout(window.flow_sidebar)
    flow_sidebar_layout.setContentsMargins(16, 18, 16, 18)
    flow_sidebar_layout.setSpacing(12)

    window.flow_sidebar_title = QLabel("Flow 管理")
    window.flow_sidebar_title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
    flow_sidebar_layout.addWidget(window.flow_sidebar_title)

    window.flow_sidebar_desc = QLabel("切换、增删改当前项目中的流程。")
    window.flow_sidebar_desc.setWordWrap(True)
    flow_sidebar_layout.addWidget(window.flow_sidebar_desc)

    flow_action_layout = QHBoxLayout()
    flow_action_layout.setContentsMargins(0, 0, 0, 0)
    flow_action_layout.setSpacing(8)

    window.add_flow_btn = QPushButton("➕")
    window.add_flow_btn.setStyleSheet(button_style("#198754"))
    window.add_flow_btn.setFixedSize(QSize(40, 40))
    window.add_flow_btn.setToolTip("新建 Flow")
    window.add_flow_btn.clicked.connect(window.add_flow)
    flow_action_layout.addWidget(window.add_flow_btn)

    window.rename_flow_btn = QPushButton("✏️")
    window.rename_flow_btn.setStyleSheet(button_style("#ffc107"))
    window.rename_flow_btn.setFixedSize(QSize(40, 40))
    window.rename_flow_btn.setToolTip("重命名当前 Flow")
    window.rename_flow_btn.clicked.connect(window.rename_flow)
    flow_action_layout.addWidget(window.rename_flow_btn)

    window.delete_flow_btn = QPushButton("🗑️")
    window.delete_flow_btn.setStyleSheet(button_style("#dc3545"))
    window.delete_flow_btn.setFixedSize(QSize(40, 40))
    window.delete_flow_btn.setToolTip("删除当前 Flow")
    window.delete_flow_btn.clicked.connect(window.delete_flow)
    flow_action_layout.addWidget(window.delete_flow_btn)
    flow_action_layout.addStretch()
    flow_sidebar_layout.addLayout(flow_action_layout)

    window.flow_list = QListWidget()
    window.flow_list.setContextMenuPolicy(Qt.CustomContextMenu)
    window.flow_list.currentItemChanged.connect(window.on_flow_selection_changed)
    window.flow_list.customContextMenuRequested.connect(window.show_flow_context_menu)
    flow_sidebar_layout.addWidget(window.flow_list)
    flow_sidebar_layout.addStretch()
    return window.flow_sidebar


def build_toolbar(window):
    toolbar = QToolBar("主工具栏")
    toolbar.setMovable(False)
    window.addToolBar(toolbar)
    window.toolbar = toolbar

    load_action = QAction("📂 加载配置", window)
    load_action.triggered.connect(window.load_config)
    toolbar.addAction(load_action)

    save_action = QAction("💾 保存配置", window)
    save_action.setShortcut(QKeySequence.Save)
    save_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
    save_action.triggered.connect(window.save_config)
    toolbar.addAction(save_action)

    toolbar.addSeparator()
    toolbar.addAction(window.undo_action)
    toolbar.addAction(window.redo_action)

    toolbar.addSeparator()

    sample_action = QAction("📝 加载示例流程", window)
    sample_action.triggered.connect(window.load_sample_flow)
    toolbar.addAction(sample_action)

    toolbar.addSeparator()

    dark_theme_action = QAction("🌙 深色", window)
    dark_theme_action.triggered.connect(lambda: window.apply_theme("dark"))
    toolbar.addAction(dark_theme_action)

    light_theme_action = QAction("☀️ 浅色", window)
    light_theme_action.triggered.connect(lambda: window.apply_theme("light"))
    toolbar.addAction(light_theme_action)

    return toolbar


def build_menu_bar(window):
    menu_bar = window.menuBar()

    file_menu = menu_bar.addMenu("文件")
    load_action = QAction("加载配置", window)
    load_action.triggered.connect(window.load_config)
    file_menu.addAction(load_action)

    save_action = QAction("保存配置", window)
    save_action.triggered.connect(window.save_config)
    file_menu.addAction(save_action)

    file_menu.addSeparator()
    sample_action = QAction("加载示例流程", window)
    sample_action.triggered.connect(window.load_sample_flow)
    file_menu.addAction(sample_action)

    edit_menu = menu_bar.addMenu("编辑")
    window.undo_action = QAction("撤销", window)
    window.undo_action.setShortcut(QKeySequence.Undo)
    window.undo_action.triggered.connect(window.undo)
    edit_menu.addAction(window.undo_action)

    window.redo_action = QAction("重做", window)
    window.redo_action.setShortcut(QKeySequence.Redo)
    window.redo_action.triggered.connect(window.redo)
    edit_menu.addAction(window.redo_action)
    edit_menu.addSeparator()

    add_node_action = QAction("添加节点", window)
    add_node_action.triggered.connect(window.add_new_node)
    edit_menu.addAction(add_node_action)

    copy_node_action = QAction("复制节点", window)
    copy_node_action.triggered.connect(window.copy_selected_node)
    edit_menu.addAction(copy_node_action)

    connect_node_action = QAction("连接节点", window)
    connect_node_action.triggered.connect(window.connect_nodes_dialog)
    edit_menu.addAction(connect_node_action)

    delete_node_action = QAction("删除节点", window)
    delete_node_action.triggered.connect(window.delete_selected_node)
    edit_menu.addAction(delete_node_action)

    view_menu = menu_bar.addMenu("查看")
    window.toggle_grid_action = QAction("显示网格", window)
    window.toggle_grid_action.setCheckable(True)
    window.toggle_grid_action.setChecked(window.flow_view.is_grid_visible())
    window.toggle_grid_action.toggled.connect(window.toggle_grid_visibility)
    view_menu.addAction(window.toggle_grid_action)

    theme_menu = view_menu.addMenu("主题")
    window.theme_action_group = QActionGroup(window)
    window.theme_action_group.setExclusive(True)
    window.dark_theme_action = QAction("黑色主题", window)
    window.dark_theme_action.setCheckable(True)
    window.light_theme_action = QAction("白色主题", window)
    window.light_theme_action.setCheckable(True)
    window.theme_action_group.addAction(window.dark_theme_action)
    window.theme_action_group.addAction(window.light_theme_action)
    window.dark_theme_action.triggered.connect(lambda checked: checked and window.apply_theme("dark"))
    window.light_theme_action.triggered.connect(lambda checked: checked and window.apply_theme("light"))
    theme_menu.addAction(window.dark_theme_action)
    theme_menu.addAction(window.light_theme_action)

    menu_bar.addMenu("调整图片")
    menu_bar.addMenu("其它")
    menu_bar.addMenu("帮助")
    return menu_bar


def build_canvas_area(window, button_style):
    left_widget = QWidget()
    left_shell_layout = QHBoxLayout(left_widget)
    left_shell_layout.setContentsMargins(0, 0, 0, 0)
    left_shell_layout.setSpacing(0)

    left_shell_layout.addWidget(build_flow_sidebar(window, button_style))

    canvas_widget = QWidget()
    left_layout = QVBoxLayout(canvas_widget)
    left_layout.setContentsMargins(0, 0, 0, 0)

    flow_header_layout = QHBoxLayout()
    window.flow_header = QLabel("📊 PyFlow 任务流程")
    window.flow_header.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
    flow_header_layout.addWidget(window.flow_header)
    flow_header_layout.addStretch()

    window.add_node_btn = QPushButton("➕ 添加节点")
    window.add_node_btn.setStyleSheet(button_style("#198754"))
    window.add_node_btn.setFixedHeight(40)
    window.add_node_btn.clicked.connect(window.add_new_node)
    flow_header_layout.addWidget(window.add_node_btn)

    window.copy_node_btn = QPushButton("📄 复制节点")
    window.copy_node_btn.setStyleSheet(button_style("#20c997"))
    window.copy_node_btn.setFixedHeight(40)
    window.copy_node_btn.clicked.connect(window.copy_selected_node)
    flow_header_layout.addWidget(window.copy_node_btn)

    window.connect_node_btn = QPushButton("🔗 连接节点")
    window.connect_node_btn.setStyleSheet(button_style("#fd7e14"))
    window.connect_node_btn.setFixedHeight(40)
    window.connect_node_btn.clicked.connect(window.connect_nodes_dialog)
    flow_header_layout.addWidget(window.connect_node_btn)

    window.delete_node_btn = QPushButton("🗑️ 删除节点")
    window.delete_node_btn.setStyleSheet(button_style("#dc3545"))
    window.delete_node_btn.setFixedHeight(40)
    window.delete_node_btn.clicked.connect(window.delete_selected_node)
    flow_header_layout.addWidget(window.delete_node_btn)

    left_layout.addLayout(flow_header_layout)

    from .canvas import FlowScene, FlowView

    window.flow_scene = FlowScene()
    window.flow_scene.node_clicked.connect(window.on_node_clicked)
    window.flow_scene.node_move_started.connect(window._on_node_change_started)
    window.flow_scene.node_position_changed.connect(window._on_node_changed)
    window.flow_scene.connection_condition_change_requested.connect(window.update_connection_condition)
    window.flow_scene.connection_delete_requested.connect(window.delete_connection)
    window.flow_scene.connection_create_requested.connect(window.create_connection_from_drag)
    window.flow_view = FlowView(window.flow_scene)
    left_layout.addWidget(window.flow_view)

    left_shell_layout.addWidget(canvas_widget, 1)
    return left_widget


def build_right_panel(window, button_style):
    right_widget = QWidget()
    right_layout = QVBoxLayout(right_widget)
    right_layout.setContentsMargins(10, 10, 10, 10)

    window.tab_widget = QTabWidget()

    from .editor import NodeEditorPanel

    window.editor_panel = NodeEditorPanel(window.task_manager)
    window.editor_panel.node_change_started.connect(window._on_node_change_started)
    window.editor_panel.node_changed.connect(window._on_node_changed)
    window.editor_panel.save_requested.connect(window.save_config)
    window.editor_panel.execute_requested.connect(window.execute_selected_node)
    window.tab_widget.addTab(window.editor_panel, "✏️ 节点编辑")

    window.log_text = QTextEdit()
    window.log_text.setReadOnly(True)
    log_widget = QWidget()
    log_layout = QVBoxLayout(log_widget)
    log_layout.setContentsMargins(0, 0, 0, 0)
    log_layout.addWidget(window.log_text)
    window.tab_widget.addTab(log_widget, "📜 执行日志")

    window.output_text = QTextEdit()
    window.output_text.setReadOnly(True)
    output_widget = QWidget()
    output_layout = QVBoxLayout(output_widget)
    output_layout.setContentsMargins(0, 0, 0, 0)
    output_layout.addWidget(window.output_text)
    window.tab_widget.addTab(output_widget, "📤 实时输出")
    window.output_tab_index = window.tab_widget.count() - 1
    right_layout.addWidget(window.tab_widget)

    bottom_layout = QHBoxLayout()
    window.reset_btn = QPushButton("🔄 重置所有状态")
    window.reset_btn.setStyleSheet(button_style("#6c757d"))
    window.reset_btn.clicked.connect(window.reset_all)
    bottom_layout.addWidget(window.reset_btn)
    bottom_layout.addStretch()

    window.execute_node_btn = QPushButton("▶️ 执行选中节点")
    window.execute_node_btn.setStyleSheet(button_style("#198754"))
    window.execute_node_btn.clicked.connect(window.execute_selected_node)
    bottom_layout.addWidget(window.execute_node_btn)

    window.execute_all_btn = QPushButton("▶️ 执行全部")
    window.execute_all_btn.setStyleSheet(button_style("#0d6efd"))
    window.execute_all_btn.clicked.connect(window.execute_all_nodes)
    bottom_layout.addWidget(window.execute_all_btn)

    window.stop_btn = QPushButton("⏹️ 停止")
    window.stop_btn.setStyleSheet(button_style("#dc3545"))
    window.stop_btn.clicked.connect(window.stop_execution)
    window.stop_btn.setEnabled(False)
    bottom_layout.addWidget(window.stop_btn)

    right_layout.addLayout(bottom_layout)
    return right_widget
