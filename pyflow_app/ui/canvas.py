import math
from typing import Dict, List, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QContextMenuEvent,
    QFont,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QTransform,
)
from PySide6.QtWidgets import QApplication, QGraphicsItem, QGraphicsScene, QGraphicsView, QMenu

from ..config import CONNECTION_CONDITION_OPTIONS
from ..models import NodeStatus, TaskFlowManager, TaskNode
from ..theme import CURRENT_THEME_NAME, THEMES, build_scrollbar_stylesheet, get_theme_palette
from ..utils import get_connection_condition_label, normalize_connection_condition


class FlowNodeItem(QGraphicsItem):
    """流程节点图形项"""

    def __init__(self, node: TaskNode, parent=None):
        super().__init__(parent)
        self.node = node
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(1)

        self.width = 280
        self.height = 150
        self.corner_radius = 15

        self.input_pos = QPointF(0, self.height / 2)
        self.output_pos = QPointF(self.width, self.height / 2)

        self.glow_intensity = 0.0
        self.is_running = False
        self.is_hovered = False
        self.highlighted_ports = set()

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        palette = get_theme_palette(getattr(self.scene(), "theme_name", None))
        status_color = self.node.get_status_color()
        selected = self.isSelected()
        skip_marked = self.node.skip_in_flow or self.node.status == NodeStatus.SKIPPED

        if self.is_running or selected or self.is_hovered:
            is_highlighted = (selected or self.is_hovered) and not self.is_running
            glow_margin = 8 if is_highlighted else 5
            glow_rect = QRectF(-glow_margin, -glow_margin, self.width + glow_margin * 2, self.height + glow_margin * 2)
            glow_path = QPainterPath()
            glow_path.addRoundedRect(glow_rect, self.corner_radius + glow_margin / 2, self.corner_radius + glow_margin / 2)
            glow_color = QColor(palette["node_highlight"]) if is_highlighted else QColor(status_color)
            glow_color.setAlphaF(0.42 if is_highlighted else 0.3 + self.glow_intensity * 0.3)
            painter.fillPath(glow_path, QBrush(glow_color))

        node_path = QPainterPath()
        node_path.addRoundedRect(0, 0, self.width, self.height, self.corner_radius, self.corner_radius)
        painter.fillPath(node_path, QBrush(QColor(palette["node_bg"])))
        if skip_marked:
            painter.save()
            painter.setClipPath(node_path)
            painter.fillPath(node_path, QBrush(QColor(255, 193, 7, 28)))
            stripe_pen = QPen(QColor(255, 214, 102, 70), 2)
            painter.setPen(stripe_pen)
            for offset in range(-self.height, self.width + self.height, 18):
                painter.drawLine(offset, self.height, offset + self.height, 0)
            painter.restore()

        border_color = QColor(palette["node_highlight"]) if (selected or self.is_hovered) and not self.is_running else QColor(status_color)
        if skip_marked and not (self.is_running or selected):
            border_color = QColor(255, 214, 102)
        pen = QPen(border_color, 4 if (selected or self.is_hovered) and not self.is_running else 3)
        if skip_marked:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawPath(node_path)

        content_x = 15
        content_y = 15
        painter.setFont(QFont("Segoe UI Emoji", 24))
        painter.drawText(QRectF(content_x, content_y, 40, 40), Qt.AlignCenter, self.node.icon)

        painter.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        painter.setPen(QColor(palette["node_text"]))
        name_rect = QRectF(content_x + 45, content_y, self.width - 70, 30)
        painter.drawText(name_rect, Qt.AlignVCenter, self.node.name)

        status_rect = QRectF(self.width - 35, 10, 25, 25)
        status_path = QPainterPath()
        status_path.addEllipse(status_rect)
        painter.fillPath(status_path, QBrush(status_color))
        if skip_marked:
            badge_rect = QRectF(self.width - 92, 12, 48, 22)
            badge_path = QPainterPath()
            badge_path.addRoundedRect(badge_rect, 8, 8)
            painter.fillPath(badge_path, QBrush(QColor(255, 193, 7, 220)))
            painter.setPen(QColor(64, 45, 0))
            painter.setFont(QFont("Microsoft YaHei", 8, QFont.Bold))
            painter.drawText(badge_rect, Qt.AlignCenter, "SKIP")

        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.setPen(QColor(palette["node_desc"]))
        desc_rect = QRectF(content_x, content_y + 45, self.width - 30, 30)
        painter.drawText(desc_rect, Qt.AlignTop | Qt.AlignLeft, self.node.description[:40] + "..." if len(self.node.description) > 40 else self.node.description)

        cmd_count = len(self.node.commands)
        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.setPen(QColor(palette["node_count"]))
        cmd_rect = QRectF(content_x, content_y + 75, self.width - 30, 20)
        painter.drawText(cmd_rect, Qt.AlignLeft, f"📝 {cmd_count} 个命令")

        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.setPen(status_color)
        status_rect = QRectF(content_x, content_y + 95, self.width - 30, 20)
        status_text = "执行时跳过" if self.node.skip_in_flow and self.node.status == NodeStatus.PENDING else self.node.get_status_text()
        painter.drawText(status_rect, Qt.AlignLeft, status_text)

        self._draw_port(painter, self.input_pos, "input", status_color)
        self._draw_port(painter, self.output_pos, "output", status_color)

    def _draw_port(self, painter: QPainter, pos: QPointF, port_name: str, color: QColor):
        palette = get_theme_palette(getattr(self.scene(), "theme_name", None))
        is_highlighted = port_name in self.highlighted_ports
        radius = 10 if is_highlighted else 8
        port_rect = QRectF(pos.x() - radius, pos.y() - radius, radius * 2, radius * 2)
        port_path = QPainterPath()
        port_path.addEllipse(port_rect)
        fill_color = QColor(palette["node_highlight"]) if is_highlighted else color
        painter.fillPath(port_path, QBrush(fill_color))
        painter.setPen(QPen(QColor(palette["node_text"]), 3 if is_highlighted else 2))
        painter.drawPath(port_path)

        if is_highlighted:
            outer_rect = QRectF(pos.x() - 15, pos.y() - 15, 30, 30)
            outer_path = QPainterPath()
            outer_path.addEllipse(outer_rect)
            highlight_color = QColor(QColor(palette["node_highlight"]))
            highlight_color.setAlpha(70)
            painter.fillPath(outer_path, QBrush(highlight_color))

    def update_status(self):
        self.update()

    def set_running(self, running: bool):
        self.is_running = running
        self.update()

    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and isinstance(self.scene(), FlowScene):
            self.scene().node_move_started.emit(self.node.id)
        super().mousePressEvent(event)

    def get_port_scene_pos(self, port_name: str) -> QPointF:
        if port_name == "input":
            return self.mapToScene(self.input_pos)
        return self.mapToScene(self.output_pos)

    def port_at_scene_pos(self, scene_pos: QPointF, tolerance: float = 16.0) -> Optional[str]:
        for port_name in ("input", "output"):
            port_pos = self.get_port_scene_pos(port_name)
            dx = port_pos.x() - scene_pos.x()
            dy = port_pos.y() - scene_pos.y()
            if (dx * dx + dy * dy) <= tolerance * tolerance:
                return port_name
        return None

    def set_highlighted_ports(self, *ports: str):
        new_ports = {port for port in ports if port}
        if new_ports != self.highlighted_ports:
            self.highlighted_ports = new_ports
            self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.node.position = {"x": float(self.pos().x()), "y": float(self.pos().y())}
            if isinstance(self.scene(), FlowScene):
                self.scene().notify_node_geometry_changed(self.node.id)
                self.scene().ensure_rect_visible(self.sceneBoundingRect())
                self.scene().node_position_changed.emit(self.node.id)
            self.scene().update()
        return super().itemChange(change, value)


class ConnectionItem(QGraphicsItem):
    """连接线"""

    def __init__(self, from_node: FlowNodeItem, to_node: FlowNodeItem,
                 from_node_id: str, to_node_id: str, condition: str = "success", parent=None):
        super().__init__(parent)
        self.from_node = from_node
        self.to_node = to_node
        self.from_node_id = from_node_id
        self.to_node_id = to_node_id
        self.condition = normalize_connection_condition(condition)
        self.is_hovered = False
        self.setZValue(0)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

    def boundingRect(self) -> QRectF:
        path_rect = self._build_path().controlPointRect()
        return path_rect.adjusted(-24, -24, 24, 24)

    def _build_path(self) -> QPainterPath:
        start = self.from_node.mapToScene(self.from_node.output_pos)
        end = self.to_node.mapToScene(self.to_node.input_pos)
        start = self.mapFromScene(start)
        end = self.mapFromScene(end)

        path = QPainterPath(start)
        ctrl1 = QPointF(start.x() + 50, start.y())
        ctrl2 = QPointF(end.x() - 50, end.y())
        path.cubicTo(ctrl1, ctrl2, end)
        return path

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(12)
        return stroker.createStroke(self._build_path())

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        path = self._build_path()
        end = path.pointAtPercent(1.0)
        palette = get_theme_palette(getattr(self.scene(), "theme_name", None))

        condition_colors = {
            "success": QColor(78, 201, 176),
            "failed": QColor(239, 83, 80),
            "always": QColor(255, 193, 7),
        }
        base_color = condition_colors.get(self.condition, QColor(100, 100, 100))
        line_color = QColor(palette["node_highlight"]) if self.is_hovered else base_color
        pen = QPen(line_color, 4 if self.is_hovered else 2)
        if self.condition == "always":
            pen.setStyle(Qt.DashLine)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawPath(path)

        self._draw_arrow(painter, end, line_color)
        self._draw_condition_badge(painter, path, line_color)

    def _draw_arrow(self, painter: QPainter, end_point: QPointF, color: QColor):
        arrow_size = 10
        arrow_path = QPainterPath()
        arrow_path.moveTo(end_point)
        arrow_path.lineTo(end_point.x() - arrow_size * 0.866, end_point.y() - arrow_size * 0.5)
        arrow_path.lineTo(end_point.x() - arrow_size * 0.866, end_point.y() + arrow_size * 0.5)
        arrow_path.closeSubpath()
        painter.fillPath(arrow_path, QBrush(color))

    def _draw_condition_badge(self, painter: QPainter, path: QPainterPath, line_color: QColor):
        palette = get_theme_palette(getattr(self.scene(), "theme_name", None))
        label = get_connection_condition_label(self.condition)
        mid_point = path.pointAtPercent(0.5)
        badge_rect = QRectF(mid_point.x() - 28, mid_point.y() - 12, 56, 24)
        badge_path = QPainterPath()
        badge_path.addRoundedRect(badge_rect, 8, 8)
        painter.fillPath(badge_path, QBrush(QColor(*palette["conn_badge_bg"])))
        painter.setPen(QPen(line_color, 1))
        painter.drawPath(badge_path)
        painter.setPen(QColor(palette["conn_badge_text"]))
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.drawText(badge_rect, Qt.AlignCenter, label)

    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)


class FlowScene(QGraphicsScene):
    """流程场景"""

    node_clicked = Signal(str)
    node_double_clicked = Signal(str)
    node_move_started = Signal(str)
    node_position_changed = Signal(str)
    connection_condition_change_requested = Signal(str, str, str, str)
    connection_delete_requested = Signal(str, str, str)
    connection_create_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme_name = CURRENT_THEME_NAME
        self.node_items: Dict[str, FlowNodeItem] = {}
        self.connection_items: List[ConnectionItem] = []
        self.task_manager: Optional[TaskFlowManager] = None
        self._dragging_connection = False
        self._drag_source_node_id: Optional[str] = None
        self._drag_source_port: Optional[str] = None
        self._drag_current_pos = QPointF()
        self._drag_target_node_id: Optional[str] = None
        self._drag_target_port: Optional[str] = None
        self._scene_padding = 600.0
        self._expand_margin = 160.0
        self._expand_step = 960.0
        self._minimum_scene_rect = QRectF(-1200.0, -1200.0, 2400.0, 2400.0)
        self.set_theme(self.theme_name)
        self.setSceneRect(self._minimum_scene_rect)

    def set_theme(self, theme_name: str):
        self.theme_name = theme_name if theme_name in THEMES else "dark"
        palette = get_theme_palette(self.theme_name)
        self.setBackgroundBrush(QColor(palette["canvas_bg"]))
        self.update()

    def _build_content_scene_rect(self) -> QRectF:
        items_rect = self.itemsBoundingRect()
        if items_rect.isNull() or items_rect.width() <= 0 or items_rect.height() <= 0:
            return QRectF(self._minimum_scene_rect)
        return items_rect.adjusted(
            -self._scene_padding,
            -self._scene_padding,
            self._scene_padding,
            self._scene_padding,
        ).united(self._minimum_scene_rect)

    def refresh_scene_rect(self):
        self.setSceneRect(self._build_content_scene_rect())

    def notify_node_geometry_changed(self, node_id: str):
        affected = False
        for connection in self.connection_items:
            if connection.from_node_id == node_id or connection.to_node_id == node_id:
                connection.prepareGeometryChange()
                connection.update()
                affected = True
        if affected:
            self.update()

    def ensure_rect_visible(self, rect: QRectF):
        target_rect = QRectF(rect)
        if target_rect.isNull():
            return

        current_rect = QRectF(self.sceneRect())
        expanded = False
        while target_rect.left() <= current_rect.left() + self._expand_margin:
            current_rect.setLeft(current_rect.left() - self._expand_step)
            expanded = True
        while target_rect.right() >= current_rect.right() - self._expand_margin:
            current_rect.setRight(current_rect.right() + self._expand_step)
            expanded = True
        while target_rect.top() <= current_rect.top() + self._expand_margin:
            current_rect.setTop(current_rect.top() - self._expand_step)
            expanded = True
        while target_rect.bottom() >= current_rect.bottom() - self._expand_margin:
            current_rect.setBottom(current_rect.bottom() + self._expand_step)
            expanded = True

        current_rect = current_rect.united(self._minimum_scene_rect)
        if not expanded and not current_rect.contains(target_rect):
            current_rect = current_rect.united(target_rect.adjusted(
                -self._scene_padding,
                -self._scene_padding,
                self._scene_padding,
                self._scene_padding,
            ))
            expanded = True

        if expanded:
            self.setSceneRect(current_rect)
            visible_rect = target_rect.adjusted(-120.0, -120.0, 120.0, 120.0)
            for view in self.views():
                view.ensureVisible(visible_rect, 80, 80)

    def load_flow(self, task_manager: TaskFlowManager):
        self.clear()
        self.node_items.clear()
        self.connection_items.clear()
        self.cancel_connection_drag()
        self.task_manager = task_manager

        y_offset = 50
        for node_id in task_manager.node_order:
            node = task_manager.nodes[node_id]
            item = FlowNodeItem(node)
            if node.position and "x" in node.position and "y" in node.position:
                item.setPos(node.position["x"], node.position["y"])
            else:
                item.setPos(50, y_offset)
                node.position = {"x": 50.0, "y": float(y_offset)}
            self.addItem(item)
            self.node_items[node_id] = item
            y_offset += item.height + 80

        for connection in task_manager.connections:
            if connection.from_id in self.node_items and connection.to_id in self.node_items:
                conn = ConnectionItem(
                    self.node_items[connection.from_id],
                    self.node_items[connection.to_id],
                    connection.from_id,
                    connection.to_id,
                    connection.normalized_condition(),
                )
                self.addItem(conn)
                self.connection_items.append(conn)

        self.refresh_scene_rect()

    def _clear_port_highlights(self):
        for item in self.node_items.values():
            item.set_highlighted_ports()

    def find_port_target(self, scene_pos: QPointF,
                         exclude_node_id: Optional[str] = None,
                         allowed_port: Optional[str] = None):
        nearest = None
        nearest_distance_sq = None
        tolerance_sq = 18.0 * 18.0
        for node_id, item in self.node_items.items():
            if exclude_node_id and node_id == exclude_node_id:
                continue
            port_names = (allowed_port,) if allowed_port else ("input", "output")
            for port_name in port_names:
                if not port_name:
                    continue
                port_pos = item.get_port_scene_pos(port_name)
                dx = port_pos.x() - scene_pos.x()
                dy = port_pos.y() - scene_pos.y()
                distance_sq = dx * dx + dy * dy
                if distance_sq <= tolerance_sq and (nearest_distance_sq is None or distance_sq < nearest_distance_sq):
                    nearest = (node_id, port_name, item)
                    nearest_distance_sq = distance_sq
        return nearest

    def is_dragging_connection(self) -> bool:
        return self._dragging_connection

    def start_connection_drag(self, node_id: str, port_name: str, scene_pos: QPointF):
        if node_id not in self.node_items:
            return False
        self._dragging_connection = True
        self._drag_source_node_id = node_id
        self._drag_source_port = port_name
        self._drag_current_pos = scene_pos
        self._drag_target_node_id = None
        self._drag_target_port = None
        self._clear_port_highlights()
        self.node_items[node_id].set_highlighted_ports(port_name)
        self.update()
        return True

    def update_connection_drag(self, scene_pos: QPointF):
        if not self._dragging_connection:
            return
        self._drag_current_pos = scene_pos
        self._clear_port_highlights()
        source_item = self.node_items.get(self._drag_source_node_id) if self._drag_source_node_id else None
        if source_item and self._drag_source_port:
            source_item.set_highlighted_ports(self._drag_source_port)

        allowed_target_port = "input" if self._drag_source_port == "output" else "output"
        target = self.find_port_target(scene_pos, exclude_node_id=self._drag_source_node_id, allowed_port=allowed_target_port)
        if target:
            node_id, port_name, item = target
            self._drag_target_node_id = node_id
            self._drag_target_port = port_name
            item.set_highlighted_ports(port_name)
        else:
            self._drag_target_node_id = None
            self._drag_target_port = None
        self.update()

    def finish_connection_drag(self):
        if not self._dragging_connection:
            return False

        created = False
        if self._drag_source_node_id and self._drag_target_node_id and self._drag_source_port and self._drag_target_port:
            if self._drag_source_port == "output" and self._drag_target_port == "input":
                self.connection_create_requested.emit(self._drag_source_node_id, self._drag_target_node_id)
                created = True
            elif self._drag_source_port == "input" and self._drag_target_port == "output":
                self.connection_create_requested.emit(self._drag_target_node_id, self._drag_source_node_id)
                created = True

        self.cancel_connection_drag()
        return created

    def cancel_connection_drag(self):
        self._dragging_connection = False
        self._drag_source_node_id = None
        self._drag_source_port = None
        self._drag_target_node_id = None
        self._drag_target_port = None
        self._clear_port_highlights()
        self.update()

    def mousePressEvent(self, event):
        if self._dragging_connection:
            event.accept()
            return
        pos = event.scenePos()
        item = self.itemAt(pos, self.views()[0].transform() if self.views() else None)
        while item:
            if isinstance(item, FlowNodeItem):
                for node_id, node_item in self.node_items.items():
                    if node_item == item:
                        self.node_clicked.emit(node_id)
                        break
                break
            item = item.parentItem()
        super().mousePressEvent(event)

    def update_node_status(self, node_id: str):
        if node_id in self.node_items:
            self.node_items[node_id].update_status()

    def set_node_running(self, node_id: str, running: bool):
        if node_id in self.node_items:
            self.node_items[node_id].set_running(running)

    def drawForeground(self, painter: QPainter, rect: QRectF):
        super().drawForeground(painter, rect)
        if not (self._dragging_connection and self._drag_source_node_id and self._drag_source_port):
            return

        source_item = self.node_items.get(self._drag_source_node_id)
        if source_item is None:
            return

        start = source_item.get_port_scene_pos(self._drag_source_port)
        end = self._drag_current_pos
        if self._drag_target_node_id and self._drag_target_port and self._drag_target_node_id in self.node_items:
            end = self.node_items[self._drag_target_node_id].get_port_scene_pos(self._drag_target_port)

        path = QPainterPath(start)
        ctrl_offset = 60
        start_offset = ctrl_offset if self._drag_source_port == "output" else -ctrl_offset
        end_offset = -ctrl_offset if (self._drag_target_port or "input") == "input" else ctrl_offset
        path.cubicTo(QPointF(start.x() + start_offset, start.y()), QPointF(end.x() + end_offset, end.y()), end)

        pen = QPen(QColor(96, 165, 250, 220), 3, Qt.DashLine)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawPath(path)

        end_circle = QRectF(end.x() - 6, end.y() - 6, 12, 12)
        end_path = QPainterPath()
        end_path.addEllipse(end_circle)
        painter.fillPath(end_path, QBrush(QColor(96, 165, 250)))

    def contextMenuEvent(self, event):
        if self._dragging_connection:
            event.accept()
            return
        item = self.itemAt(event.scenePos(), self.views()[0].transform() if self.views() else QTransform())
        while item:
            if isinstance(item, ConnectionItem):
                menu = QMenu()
                condition_menu = menu.addMenu("修改条件")
                condition_actions = {}
                for condition_value, condition_label in CONNECTION_CONDITION_OPTIONS:
                    action = condition_menu.addAction(condition_label)
                    action.setCheckable(True)
                    action.setChecked(condition_value == item.condition)
                    if condition_value == item.condition:
                        action.setEnabled(False)
                    condition_actions[action] = condition_value
                menu.addSeparator()
                delete_action = menu.addAction("删除连接")
                chosen_action = menu.exec(event.screenPos())
                if chosen_action in condition_actions:
                    self.connection_condition_change_requested.emit(
                        item.from_node_id,
                        item.to_node_id,
                        item.condition,
                        condition_actions[chosen_action],
                    )
                    event.accept()
                    return
                if chosen_action == delete_action:
                    self.connection_delete_requested.emit(item.from_node_id, item.to_node_id, item.condition)
                    event.accept()
                    return
                break
            item = item.parentItem()
        super().contextMenuEvent(event)


class FlowView(QGraphicsView):
    """流程视图"""

    def __init__(self, scene: FlowScene, parent=None):
        super().__init__(scene)
        self._grid_visible = True
        self.theme_name = CURRENT_THEME_NAME
        self._background_color = QColor()
        self._minor_grid_color = QColor()
        self._major_grid_color = QColor()
        self._minor_grid_size = 24
        self._major_grid_size = 120
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setRubberBandSelectionMode(Qt.IntersectsItemShape)
        self.set_theme(self.theme_name)
        self.setMouseTracking(True)

        self._drag_mode = False
        self._last_pos = None
        self._dragging_node = False
        self._right_drag_origin = None
        self._rubber_band_active = False
        self._edge_pan_margin = 48
        self._edge_pan_max_speed = 36

    def set_grid_visible(self, visible: bool):
        if self._grid_visible != visible:
            self._grid_visible = visible
            self.viewport().update()

    def is_grid_visible(self) -> bool:
        return self._grid_visible

    def set_theme(self, theme_name: str):
        self.theme_name = theme_name if theme_name in THEMES else "dark"
        palette = get_theme_palette(self.theme_name)
        self._background_color = QColor(palette["canvas_bg"])
        self._minor_grid_color = QColor(palette["grid_minor"])
        self._major_grid_color = QColor(palette["grid_major"])
        self.setStyleSheet(f"""
            QGraphicsView {{
                background-color: {palette['canvas_bg']};
                border: none;
            }}
        """ + build_scrollbar_stylesheet(self.theme_name, "QGraphicsView"))
        self.viewport().update()

    def _edge_pan_delta(self, position: int, span: int) -> int:
        if span <= 0:
            return 0
        if position < self._edge_pan_margin:
            ratio = (self._edge_pan_margin - position) / float(self._edge_pan_margin)
            return -max(1, int(self._edge_pan_max_speed * ratio))
        distance_to_far_edge = span - position
        if distance_to_far_edge < self._edge_pan_margin:
            ratio = (self._edge_pan_margin - distance_to_far_edge) / float(self._edge_pan_margin)
            return max(1, int(self._edge_pan_max_speed * ratio))
        return 0

    def _auto_pan_for_edge_drag(self, view_pos) -> bool:
        viewport = self.viewport().rect()
        dx = self._edge_pan_delta(view_pos.x(), viewport.width())
        dy = self._edge_pan_delta(view_pos.y(), viewport.height())
        if dx == 0 and dy == 0:
            return False
        if dx:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + dx)
        if dy:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + dy)
        return True

    def drawBackground(self, painter: QPainter, rect: QRectF):
        painter.fillRect(rect, self._background_color)
        if not self._grid_visible:
            return

        left = math.floor(rect.left())
        right = math.ceil(rect.right())
        top = math.floor(rect.top())
        bottom = math.ceil(rect.bottom())
        minor_lines = []
        major_lines = []

        first_x = left - (left % self._minor_grid_size)
        first_y = top - (top % self._minor_grid_size)
        for x in range(first_x, right + self._minor_grid_size, self._minor_grid_size):
            line = (QPointF(x, top), QPointF(x, bottom))
            (major_lines if x % self._major_grid_size == 0 else minor_lines).append(line)
        for y in range(first_y, bottom + self._minor_grid_size, self._minor_grid_size):
            line = (QPointF(left, y), QPointF(right, y))
            (major_lines if y % self._major_grid_size == 0 else minor_lines).append(line)

        if minor_lines:
            painter.setPen(QPen(self._minor_grid_color, 1))
            for start, end in minor_lines:
                painter.drawLine(start, end)
        if major_lines:
            painter.setPen(QPen(self._major_grid_color, 1))
            for start, end in major_lines:
                painter.drawLine(start, end)

    def wheelEvent(self, event):
        factor = 1.1 if event.angleDelta().y() >= 0 else 1.0 / 1.1
        self.scale(factor, factor)
        event.accept()

    def mousePressEvent(self, event):
        scene = self.scene()
        view_pos = event.position().toPoint()
        if event.button() == Qt.RightButton:
            self._drag_mode = False
            self._last_pos = view_pos
            self._right_drag_origin = view_pos
            self._dragging_node = False
            self._rubber_band_active = False
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            if isinstance(scene, FlowScene):
                port_target = scene.find_port_target(self.mapToScene(view_pos))
                if port_target:
                    node_id, port_name, _item = port_target
                    scene.node_clicked.emit(node_id)
                    self._dragging_node = False
                    scene.start_connection_drag(node_id, port_name, self.mapToScene(view_pos))
                    self.setDragMode(QGraphicsView.NoDrag)
                    event.accept()
                    return

            item = self.scene().itemAt(self.mapToScene(view_pos), self.transform())
            if item and isinstance(item, FlowNodeItem):
                self._dragging_node = True
                self._rubber_band_active = False
                self.setDragMode(QGraphicsView.NoDrag)
                QGraphicsView.mousePressEvent(self, event)
            elif item:
                self._dragging_node = False
                self._rubber_band_active = False
                self.setDragMode(QGraphicsView.NoDrag)
                QGraphicsView.mousePressEvent(self, event)
            else:
                self._drag_mode = False
                self._dragging_node = False
                self._rubber_band_active = True
                self.setDragMode(QGraphicsView.RubberBandDrag)
                QGraphicsView.mousePressEvent(self, event)
            return

        QGraphicsView.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        scene = self.scene()
        view_pos = event.position().toPoint()
        if isinstance(scene, FlowScene) and scene.is_dragging_connection():
            scene.update_connection_drag(self.mapToScene(view_pos))
            event.accept()
            return
        if self._right_drag_origin is not None and event.buttons() & Qt.RightButton:
            if not self._drag_mode and (view_pos - self._right_drag_origin).manhattanLength() >= QApplication.startDragDistance():
                self._drag_mode = True
                self._last_pos = view_pos
                self.setCursor(Qt.ClosedHandCursor)
            if self._drag_mode and self._last_pos:
                delta = view_pos - self._last_pos
                self._last_pos = view_pos
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        if self._drag_mode and self._last_pos:
            delta = view_pos - self._last_pos
            self._last_pos = view_pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            QGraphicsView.mouseMoveEvent(self, event)
            if isinstance(scene, FlowScene) and self._dragging_node and event.buttons() & Qt.LeftButton:
                self._auto_pan_for_edge_drag(view_pos)

    def mouseReleaseEvent(self, event):
        scene = self.scene()
        view_pos = event.position().toPoint()
        if event.button() == Qt.LeftButton and isinstance(scene, FlowScene) and scene.is_dragging_connection():
            scene.update_connection_drag(self.mapToScene(view_pos))
            scene.finish_connection_drag()
            self._dragging_node = False
            event.accept()
            return
        if event.button() == Qt.RightButton and self._right_drag_origin is not None:
            was_dragging_view = self._drag_mode
            self._drag_mode = False
            self._right_drag_origin = None
            self._last_pos = None
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.ArrowCursor)
            if was_dragging_view:
                event.accept()
                return
            context_event = QContextMenuEvent(
                QContextMenuEvent.Mouse,
                view_pos,
                event.globalPosition().toPoint(),
                event.modifiers(),
            )
            QApplication.sendEvent(self.viewport(), context_event)
            event.accept()
            return

        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self._dragging_node = False
            if self._rubber_band_active:
                self._rubber_band_active = False
                self.setDragMode(QGraphicsView.NoDrag)
