"""Interactive historical capital-point map, not fabricated Ming borders."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView

from dynasty.content import HistoryRepository, read_json


def project(lon: float, lat: float) -> QPointF:
    return QPointF((lon - 72) * 17, (54 - lat) * 21)


class ProvinceMap(QGraphicsView):
    region_selected = Signal(str)

    def __init__(self, repository: HistoryRepository, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.setObjectName("provinceMap")
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QColor("#dfe9df"))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.bounds = QRectF(0, 0, (138 - 72) * 17, (54 - 15) * 21)
        self.scene().setSceneRect(self.bounds)
        self.dots = {}
        self._zoom = 1.0
        self._draw_basemap()
        self._draw_regions()

    def _draw_basemap(self) -> None:
        land = read_json(self.repository.directory / "raw/geography/ne_110m_land.geojson", {})
        for feature in land.get("features", []):
            geometry = feature.get("geometry", {})
            polygons = geometry.get("coordinates", [])
            if geometry.get("type") == "Polygon":
                polygons = [polygons]
            if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
                continue
            path = QPainterPath()
            for polygon in polygons:
                for ring in polygon:
                    if not ring:
                        continue
                    path.moveTo(project(*ring[0][:2]))
                    for coordinate in ring[1:]:
                        path.lineTo(project(*coordinate[:2]))
                    path.closeSubpath()
            self.scene().addPath(path, QPen(QColor("#b7c8b0"), 1), QColor("#eff0dc"))
        for lon in range(80, 139, 10):
            x = project(lon, 54).x()
            self.scene().addLine(x, 0, x, self.bounds.height(), QPen(QColor("#cdd9c9"), .6, Qt.PenStyle.DotLine))
        for lat in range(20, 55, 10):
            y = project(72, lat).y()
            self.scene().addLine(0, y, self.bounds.width(), y, QPen(QColor("#cdd9c9"), .6, Qt.PenStyle.DotLine))
        label = self.scene().addText("北 ↑", QFont("Noto Sans SC", 11))
        label.setDefaultTextColor(QColor("#557366"))
        label.setPos(28, 25)
        sea = self.scene().addText("东 海", QFont("Noto Sans SC", 16))
        sea.setDefaultTextColor(QColor("#99b4a5"))
        sea.setPos(project(128, 28))

    def _draw_regions(self) -> None:
        for row in self.repository.regions:
            longitude = row.get("longitude")
            latitude = row.get("latitude")
            if longitude is None or latitude is None:
                continue
            point = project(float(longitude), float(latitude))
            dot = self.scene().addEllipse(-7, -7, 14, 14, QPen(QColor("#fffdf0"), 2), QColor("#417461"))
            dot.setPos(point)
            dot.setData(0, row["id"])
            dot.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            dot.setZValue(5)
            dot.setToolTip(f"{row['name']}\n治所参考点 · 点击查看行政名录")
            label = self.scene().addText(row.get("short_name", row["name"]), QFont("Noto Sans SC", 11))
            label.setDefaultTextColor(QColor("#294a3a"))
            label.setPos(point + QPointF(10, -13))
            label.setData(0, row["id"])
            label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            label.setZValue(6)
            self.dots[row["id"]] = dot

    def select_region(self, identifier: str) -> None:
        for key, dot in self.dots.items():
            dot.setBrush(QColor("#b56b3e" if key == identifier else "#417461"))
            dot.setPen(QPen(QColor("#fff8db"), 3 if key == identifier else 2))

    def mousePressEvent(self, event) -> None:
        self._press_pos = event.position()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if hasattr(self, "_press_pos") and (event.position() - self._press_pos).manhattanLength() < 5:
            item = self.itemAt(event.position().toPoint())
            if item is not None and item.data(0):
                self.region_selected.emit(item.data(0))
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        next_zoom = self._zoom * factor
        if .7 <= next_zoom <= 5:
            self.scale(factor, factor)
            self._zoom = next_zoom

    def reset_view(self) -> None:
        self.fitInView(self.bounds, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = 1

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._zoom == 1:
            self.reset_view()
