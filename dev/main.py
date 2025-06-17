import sys, io, time
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QIcon, QImage, QPixmap, QTransform
from PyQt5.QtCore import QSize, QBuffer, Qt
from PyQt5.QtWidgets import QFileDialog, QColorDialog, QDialog, QLabel
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QApplication
from PyQt5.QtWidgets import QMessageBox, QInputDialog, QActionGroup
from PIL import Image, ImageEnhance, ImageChops, ImageQt, ImageFilter, ImageOps, ImageDraw, ImageFont
import PIL.ImageQt as ImageQt
from ui2 import Ui_MainWindow
from about import Ui_Dialog
import res


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.initialize_properties()
        self.setup_ui()
        self.setup_connections()
        self.setup_collapsible_panels()
        self.add_shadows()
        

    def initialize_properties(self):
        self.original_image = None
        self.working_pil_image = None
        self.original_pixmap = None
        self.unsaved_img = None
        self.current_file_path = None
        self.enabled_cropping = False
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self.zoom_step = 0.25
        self.panning = False
        self.last_pan_point = QtCore.QPoint()
        self.rubber_band = None
        self.crop_origin = None
        self.rect_moved = False
        self.undo_stack = []
        self.redo_stack = []
        self.max_stack_size = 5
        self.max_viewport_size = QtCore.QSize(800, 600)
        self.current_tool = None  # 'text' or 'crop'

    def setup_ui(self):
        self.ui.imageLabel = self.ui.scrollArea_viewport.findChild(QLabel, "imageLabel")
        self.ui.imageLabel.setAlignment(QtCore.Qt.AlignCenter)

        self.ui.scrollArea_viewport.setAlignment(QtCore.Qt.AlignCenter)
        self.ui.scrollArea_viewport.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff
        )
        self.ui.scrollArea_viewport.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff
        )

    def setup_connections(self):
        # Menu actions
        self.ui.actionOpen.triggered.connect(self.open_file)
        self.ui.actionCrop.triggered.connect(lambda: self.set_tool('crop'))
        self.ui.actionRotate.triggered.connect(self.rotate_img)
        self.ui.actionResize.triggered.connect(self.resize_img)
        self.ui.actionMirror.triggered.connect(self.mirror_img)
        self.ui.actionAbout.triggered.connect(self.show_about_dialog)
        self.ui.actionUndo.triggered.connect(self.undo)
        self.ui.actionRedo.triggered.connect(self.redo)
        self.ui.actionSave.triggered.connect(self.save_image)
        self.ui.actionSave_as.triggered.connect(self.save_image_as)
        self.ui.actionTextTool.triggered.connect(lambda: self.set_tool('text'))
        # Zoom slider
        # self.ui.zoomInButton.clicked.connect(self.zoom_in)
        # self.ui.zoomOutButton.clicked.connect(self.zoom_out)
        self.ui.zoomSlider.valueChanged.connect(self.zoom)

        # Right toolbar---------------------------------------------------------------------
        # Color
        self.ui.r_slider.valueChanged.connect(self.update_full_image)
        self.ui.g_slider.valueChanged.connect(self.update_full_image)
        self.ui.b_slider.valueChanged.connect(self.update_full_image)
        
        self.ui.reset_color_button.clicked.connect(self.reset_colors)
        
        # Enhancements
        self.ui.brightness_slider.valueChanged.connect(self.update_full_image)
        self.ui.contrast_slider.valueChanged.connect(self.update_full_image)
        self.ui.sharpness_slider.valueChanged.connect(self.update_full_image)
        self.ui.saturation_slider.valueChanged.connect(self.update_full_image)

        self.ui.reset_enhance_button.clicked.connect(self.reset_enhancements)
        # Img filters
        self.ui.actionBlur.toggled.connect(self.update_full_image)
        self.ui.actionContour.toggled.connect(self.update_full_image)
        self.ui.actionDetail.toggled.connect(self.update_full_image)
        self.ui.actionEdge_Enhance.toggled.connect(self.update_full_image)
        self.ui.actionSharpen.toggled.connect(self.update_full_image)
        self.ui.actionEmboss.toggled.connect(self.update_full_image)
        self.ui.actionFind_Edhes.toggled.connect(self.update_full_image)
        self.ui.actionSmooth.toggled.connect(self.update_full_image)
        
        #Img Actions
        # Event filters
        self.ui.scrollArea_viewport.viewport().installEventFilter(self)
        #-----------------------------------------------------------------------------------
    def setup_collapsible_panels(self):
        layout = self.ui.verticalLayout_2
        for i in reversed(range(layout.count())):
            if item := layout.itemAt(i):
                if widget := item.widget():
                    widget.setParent(None)

        self.panels = [
            CollapsiblePanel("Color", self.ui.collapsible_1),
            CollapsiblePanel("Enhancements", self.ui.collapsible_2),
        ]

        for panel in self.panels:
            layout.addWidget(panel)

        layout.addStretch(1)

    def add_shadows(self):
        self.add_shadow(self.ui.scrollArea)

    # ================ Image Operations =================
    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open File", "", "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if not file_path:
            return

        self.original_image = Image.open(file_path)
        self.current_file_path = file_path  # 🔹 зберігаємо шлях
        self.base_image = self.original_image.copy()
        self.working_pil_image = self.original_image.copy()
        self.original_pixmap = self.pil_image_to_pixmap(self.working_pil_image)
        self.zoom_factor = 1.0
        self.ui.choosefileLabel.setParent(None) # usuń tekst "Choose File"
        self.update_display()
        self.ui.statusbar.showMessage(f"Opened: {file_path}")

    def pil_image_to_pixmap(self, pil_image):
        if not pil_image:
            return QtGui.QPixmap()

        if pil_image.mode != "RGBA":
            pil_image = pil_image.convert("RGBA")


        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(buffer.getvalue())
        return pixmap

    def apply_all_adjustments(self, image):
        image = self.update_colors(image)
        image = self.update_enhancements(image)
        image = self.update_filters(image)
        return image

    def update_full_image(self):
        if not hasattr(self, 'base_image') or self.base_image is None:
            return

        image = self.base_image.convert("RGB")

        image = self.apply_all_adjustments(image)

        self.working_pil_image = image.copy()
        self.original_pixmap = self.pil_image_to_pixmap(image)
        self.update_display()

    def update_colors(self, image):
        red_factor = self.ui.r_slider.value() / 100
        green_factor = self.ui.g_slider.value() / 100
        blue_factor = self.ui.b_slider.value() / 100

        r, g, b = image.split()
        r = r.point(lambda i: max(0, min(255, int(i * red_factor))))
        g = g.point(lambda i: max(0, min(255, int(i * green_factor))))
        b = b.point(lambda i: max(0, min(255, int(i * blue_factor))))
        return Image.merge("RGB", (r, g, b))

    def update_enhancements(self, image):
        brightness_value = self.ui.brightness_slider.value() / 20
        contrast_value = self.ui.contrast_slider.value() / 20
        sharpness_value = self.ui.sharpness_slider.value() / 20
        saturation_value = self.ui.saturation_slider.value() / 20

        image = ImageEnhance.Brightness(image).enhance(2 ** brightness_value)
        image = ImageEnhance.Contrast(image).enhance(3 ** contrast_value)
        image = ImageEnhance.Sharpness(image).enhance(3 ** sharpness_value)
        image = ImageEnhance.Color(image).enhance(3 ** saturation_value)

        return image

    def update_filters(self, image):
        filter_map = {
            self.ui.actionBlur: ImageFilter.BLUR,
            self.ui.actionContour: ImageFilter.CONTOUR,
            self.ui.actionDetail: ImageFilter.DETAIL,
            self.ui.actionEdge_Enhance: ImageFilter.EDGE_ENHANCE,
            self.ui.actionSharpen: ImageFilter.SHARPEN,
            self.ui.actionEmboss: ImageFilter.EMBOSS,
            self.ui.actionFind_Edhes: ImageFilter.FIND_EDGES,
            self.ui.actionSmooth: ImageFilter.SMOOTH,
        }

        for action, pil_filter in filter_map.items():
            if action.isChecked():
                image = image.filter(pil_filter)

        return image
    
    def reset_enhancements(self):
        self.ui.brightness_slider.setValue(0)
        self.ui.contrast_slider.setValue(0)
        self.ui.sharpness_slider.setValue(0)
        self.ui.saturation_slider.setValue(0)

        try:
            self.current_image = self.original_image.copy()
            self.update_display()

        except Exception as e:
            print(f"Error: {e}")
            return

    def reset_colors(self):
        self.ui.r_slider.setValue(100)
        self.ui.g_slider.setValue(100)
        self.ui.b_slider.setValue(100)

        try:
            self.current_image = self.original_image.copy()
            self.update_display()

        except Exception as e:
            print(f"Error: {e}")
            return

    def rotate_img(self):
        angle, ok = self.input_dialog(QInputDialog.DoubleInput, "Rotate Image", "Enter rotation angle (0-360):", 0,
                                      0, 360, 0)
        if ok:
            self.push_undo_state()
            self.base_image = self.base_image.rotate(-angle, expand=True)
            self.update_full_image()

    def input_dialog(self, type, title, text, decimals=1, min=0, max=360, val=0, items=None):
        dialog = QInputDialog(self)
        dialog.setWindowTitle(title)
        dialog.setLabelText(text)
        dialog.setInputMode(type)
        if type == QInputDialog.DoubleInput:
            dialog.setDoubleDecimals(decimals)
            dialog.setDoubleMinimum(min)
            dialog.setDoubleMaximum(max)
            dialog.setDoubleValue(val)
        elif type == QInputDialog.TextInput:
            pass
        else:  # ComboBox
            dialog.setComboBoxEditable(False)
            dialog.setComboBoxItems(items)


        dialog.setStyleSheet("color: #dddddd;")
        dialog.show()
        if dialog.exec_() == QInputDialog.Accepted:
            if type == QInputDialog.DoubleInput:
                return dialog.doubleValue(), True
            elif type == QInputDialog.TextInput:
                return dialog.textValue(), True
            else:
                return dialog.textValue(), True
        else:
            return None, False
    
    def show_info(self, title, message):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setStyleSheet("color: #dddddd;")

        msg_box.exec_()

    def resize_img(self):
        factor, ok = self.input_dialog(QInputDialog.DoubleInput, "Resize Image", "Resize factor (e.g. 2 = half size):", 
                          2, 0.1, 1000, 1.0)
        if ok:
            self.push_undo_state()
            old_size = self.base_image.size
            new_size = (int(old_size[0] / factor), int(old_size[1] / factor))

            self.base_image = self.base_image.resize(new_size, Image.Resampling.LANCZOS)

            self.show_info("Resize Info", f"Original size: {old_size[0]}x{old_size[1]}\n" + 
                           f"New size: {new_size[0]}x{new_size[1]}")

            self.update_full_image()

    def mirror_img(self):
        mode, ok = self.input_dialog(None, "Mirror Image", "Choose mirror direction:", 
                                     items=["Horizontal", "Vertical", "Both"])
        if not ok:
            return
        self.push_undo_state()
        if mode == "Horizontal":
            new_image = ImageOps.mirror(self.base_image)
        elif mode == "Vertical":
            new_image = ImageOps.flip(self.base_image)
        else:  # Both
            new_image = ImageOps.mirror(self.base_image)
            new_image = ImageOps.flip(new_image)

        self.base_image = new_image
        self.update_full_image()


    def save_image(self):
        if not self.current_file_path:
            self.save_image_as()
            return

        try:
            self.working_pil_image.save(self.current_file_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save image:\n{e}")

    def save_image_as(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Image As", "", "Images (*.png *.jpg *.bmp)")
        if not file_path:
            return

        try:
            self.working_pil_image.save(file_path)
            self.current_file_path = file_path  # оновлюємо шлях
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save image:\n{e}")

    # def zoom_in(self):
    #     self.zoom_factor = min(self.zoom_factor + self.zoom_step, self.max_zoom)
    #     self.update_display()
    #
    # def zoom_out(self):
    #     self.zoom_factor = max(self.zoom_factor - self.zoom_step, self.min_zoom)
    #     self.update_display()

    def set_tool(self, tool_name):
        print(tool_name)
        if self.current_tool != tool_name:
            self.current_tool = tool_name
            self.ui.statusbar.showMessage(f"Aktywne narzędzie: {tool_name}")
        else:
            self.current_tool = None
        print(self.current_tool)

    def add_text_on_image(self, pos_in_label):
        if not self.working_pil_image:
            return

        coords = self._get_image_coords(pos_in_label)
        if not coords:
            return

        text, ok = self.input_dialog(QInputDialog.TextInput, "Add text", "Type text:")

        if ok and text:
            self.push_undo_state()
            draw = ImageDraw.Draw(self.working_pil_image)

            font_size = 40
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except IOError:
                font = ImageFont.load_default()
            draw.text(coords, text, font=font, fill=QtGui.QColor('black').name())

            self.push_undo_state()
            self.base_image = self.working_pil_image.copy()
            self.original_pixmap = self.pil_image_to_pixmap(self.working_pil_image)
            self.update_display()

    def _get_image_coords(self, pos_in_label):
        if not self.original_pixmap or self.original_pixmap.isNull():
            return None
        pixmap_size = self.ui.imageLabel.pixmap().size()
        image_size = self.working_pil_image.size

        if pixmap_size.width() == 0 or pixmap_size.height() == 0:
            return None
        scale_x = image_size[0] / pixmap_size.width()
        scale_y = image_size[1] / pixmap_size.height()

        img_x = int(pos_in_label.x() * scale_x)
        img_y = int(pos_in_label.y() * scale_y)
        return (img_x, img_y)

    def zoom(self, value):
        if not self.original_pixmap or self.original_pixmap.isNull():
            return
        max_height, max_width = self.size().height() * 0.8, self.size().width() * 0.8
        vertical_ratio = max_height / self.original_pixmap.height()
        horizontal_ratio = max_width / self.original_pixmap.width()
        if vertical_ratio >= horizontal_ratio:
            self.zoom_factor = vertical_ratio
        else:
            self.zoom_factor = horizontal_ratio
        self.zoom_factor *= value / 100
        percent = self.zoom_factor * 100
        self.ui.zoomLabel.setText(f"{int(percent)}%")
        self.update_display()

    # ================ Undo/Redo Operations =================
    def push_undo_state(self):
        if not self.base_image:
            return

        self.undo_stack.append(self.base_image.copy())
        if len(self.undo_stack) > self.max_stack_size:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            self.ui.statusbar.showMessage("Nothing to undo")
            return

        self.redo_stack.append(self.base_image.copy())
        self.base_image = self.undo_stack.pop()
        
        self.update_full_image()
        self.ui.statusbar.showMessage("Undo successful")

    def redo(self):
        if not self.redo_stack:
            self.ui.statusbar.showMessage("Nothing to redo")
            return
            
        self.undo_stack.append(self.base_image.copy())        
        self.base_image = self.redo_stack.pop()

        self.update_full_image()
        self.ui.statusbar.showMessage("Redo successful")

    # ================ Display Operations =================
    def update_display(self):
        if not self.original_pixmap or self.original_pixmap.isNull():
            return
        scaled_size = self.original_pixmap.size() * self.zoom_factor
        scaled_pixmap = self.original_pixmap.scaled(
            scaled_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
        )

        self.ui.imageLabel.setPixmap(scaled_pixmap)
        # viewport_size = scaled_size.boundedTo(self.max_viewport_size)
        self.ui.imageLabel.resize(scaled_pixmap.size())

        # Set scroll area size
        self.ui.scrollArea_viewport.setMinimumSize(
            min(scaled_size.width(), self.max_viewport_size.width()),
            min(scaled_size.height(), self.max_viewport_size.height()),
        )
        self.ui.scrollArea_viewport.setMaximumSize(self.max_viewport_size)

    def add_shadow(
        self,
        widget,
        blur_radius=15,
        x_offset=5,
        y_offset=5,
        color=QtGui.QColor(0, 0, 0, 160),
    ):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(blur_radius)
        shadow.setXOffset(x_offset)
        shadow.setYOffset(y_offset)
        shadow.setColor(color)
        widget.setGraphicsEffect(shadow)

    # ================ Crop and text =================

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        pos_in_viewport = self.ui.imageLabel.mapFrom(self, event.pos())
        if (
            self.working_pil_image
            and event.button() == QtCore.Qt.LeftButton
            and self.current_tool == 'crop'
        ):

            self.rect_moved = False
        
            if (
                self.ui.imageLabel.rect().contains(pos_in_viewport)
                and self.ui.imageLabel.pixmap()
                and not self.ui.imageLabel.pixmap().isNull()
            ):

                self.crop_origin = pos_in_viewport
                if not self.rubber_band:
                    self.rubber_band = QtWidgets.QRubberBand(
                        QtWidgets.QRubberBand.Rectangle, self.ui.imageLabel
                    )
                self.rubber_band.setGeometry(
                    QtCore.QRect(self.crop_origin, QtCore.QSize())
                )
                self.rubber_band.show()
                event.accept()
                return
        elif self.working_pil_image and event.button() == QtCore.Qt.LeftButton:
            if self.current_tool == 'text':
                self.add_text_on_image(pos_in_viewport)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if self.crop_origin and self.rubber_band and self.current_tool == 'crop':
            self.rect_moved = True
            current_pos_in_viewport = self.ui.imageLabel.mapFrom(self, event.pos())
            self.rubber_band.setGeometry(
                QtCore.QRect(self.crop_origin, current_pos_in_viewport).normalized()
            )
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if (
            self.current_tool == 'crop'
            and self.crop_origin
            and self.rubber_band
            and self.rect_moved
            and event.button() == QtCore.Qt.LeftButton
        ):

            end_pos_in_viewport = self.ui.imageLabel.mapFrom(self, event.pos())
            selection_rect_vp_coords = QtCore.QRect(
                self.crop_origin, end_pos_in_viewport
            ).normalized()
            self.rect_moved = False
            selection_rect_vp_coords = selection_rect_vp_coords.intersected(
                self.ui.imageLabel.rect()
            )
            self.rubber_band.hide()

            current_display_pixmap = self.ui.imageLabel.pixmap()
            if (
                self.working_pil_image
                and current_display_pixmap
                and not current_display_pixmap.isNull()
                and selection_rect_vp_coords.isValid()
                and selection_rect_vp_coords.width() > 0
                and selection_rect_vp_coords.height() > 0
            ):

                pixmap_size = current_display_pixmap.size()
                image_size = self.working_pil_image.size
                scale_x = image_size[0] / pixmap_size.width()
                scale_y = image_size[1] / pixmap_size.height()


                x = int(selection_rect_vp_coords.x() * scale_x)
                y = int(selection_rect_vp_coords.y() * scale_y)
                w = int(selection_rect_vp_coords.width() * scale_x)
                h = int(selection_rect_vp_coords.height() * scale_y)
                crop_box = (x, y, x + w, y + h)
                self.push_undo_state()
                self.base_image = self.base_image.crop(crop_box)

                self.update_full_image()

                self.ui.zoomSlider.setValue(100)

            self.crop_origin = None
            event.accept()
            return

        if self.rubber_band:
            self.rubber_band.hide()
        self.crop_origin = None
        super().mouseReleaseEvent(event)


    def process_crop(self, selection_rect, displayed_pixmap):
        if not self.working_pil_image or not displayed_pixmap:
            return

        pixmap_width = displayed_pixmap.width()
        pixmap_height = displayed_pixmap.height()

        image_width, image_height = self.working_pil_image.size

        scale_x = image_width / pixmap_width
        scale_y = image_height / pixmap_height

        left = int(selection_rect.left() * scale_x)
        upper = int(selection_rect.top() * scale_y)
        right = int(selection_rect.right() * scale_x)
        lower = int(selection_rect.bottom() * scale_y)

        left = max(0, min(left, image_width))
        right = max(0, min(right, image_width))
        upper = max(0, min(upper, image_height))
        lower = max(0, min(lower, image_height))

        if right - left > 0 and lower - upper > 0:
            self.push_undo_state()
            cropped_image = self.working_pil_image.crop((left, upper, right, lower))
            self.working_pil_image = cropped_image.copy()
            self.original_pixmap = self.pil_image_to_pixmap(cropped_image)
            self.zoom_factor = 1.0
            self.update_display()
            self.ui.statusbar.showMessage("Cropped image.")
        else:
            self.ui.statusbar.showMessage("Invalid crop area.")


    # ================ Event Handling =================
    def eventFilter(self, source, event):
        if source is self.ui.scrollArea_viewport.viewport():
            if event.type() == QtCore.QEvent.MouseButtonPress:
                if event.buttons() == QtCore.Qt.MiddleButton:
                    self.panning = True
                    self.last_pan_point = event.pos()
                    QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.ClosedHandCursor)
                    return True

            elif event.type() == QtCore.QEvent.MouseMove and self.panning:
                delta = event.pos() - self.last_pan_point
                self.last_pan_point = event.pos()
                h_bar = self.ui.scrollArea_viewport.horizontalScrollBar()
                v_bar = self.ui.scrollArea_viewport.verticalScrollBar()
                h_bar.setValue(h_bar.value() - delta.x())
                v_bar.setValue(v_bar.value() - delta.y())
                return True

            elif event.type() == QtCore.QEvent.MouseButtonRelease:
                if event.button() == QtCore.Qt.MiddleButton and self.panning:
                    self.panning = False
                    QtWidgets.QApplication.restoreOverrideCursor()
                    return True

        return super().eventFilter(source, event)

    def show_about_dialog(self):
        dialog = AboutDialog(self)
        dialog.exec_()

    # ================ About window =================


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle("About")
        self.setFixedSize(self.size())


class CollapsiblePanel(QtWidgets.QWidget):
    def __init__(self, title: str, content: QtWidgets.QWidget, parent=None):
        super().__init__(parent)

        self.toggle_button = QtWidgets.QToolButton(
            text=title, checkable=True, checked=False
        )
        self.toggle_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(QtCore.Qt.RightArrow)
        self.toggle_button.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self.toggle_button.clicked.connect(self.toggle)
        self.toggle_button.setStyleSheet(
            """
            QToolButton {
                background-color: #444;
                color: white;
                border: none;
                padding: 5px;
                text-align: left;
                font-weight: bold;
            }
            QToolButton:checked {
                background-color: #666;
            }
            QToolButton::menu-indicator { image: none; }
        """
        )

        self.content_area = QtWidgets.QScrollArea()
        self.content_area.setMaximumHeight(0)
        self.content_area.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self.content_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.content_area.setStyleSheet("background-color: #666;")
        self.content_area.setWidgetResizable(True)
        self.content_area.setWidget(content)

        self.toggle_animation = QtCore.QPropertyAnimation(
            self.content_area, b"maximumHeight"
        )
        self.toggle_animation.setDuration(200)
        self.toggle_animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        self.stretch = QtWidgets.QSpacerItem(
            20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.toggle_button)
        main_layout.addWidget(self.content_area)
        main_layout.addItem(self.stretch)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

    def toggle(self):
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(
            QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow
        )
        content_height = self.content_area.widget().sizeHint().height()
        self.toggle_animation.setStartValue(self.content_area.maximumHeight())
        self.toggle_animation.setEndValue(content_height if checked else 0)
        self.toggle_animation.start()

        if checked:
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding
            )
            self.content_area.setSizePolicy(
                QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding
            )
        else:
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum
            )
            self.content_area.setSizePolicy(
                QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed
            )


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    splash_pix = QtGui.QPixmap(":/newPrefix/Ikony_inż/icon100.png")
    splash = QtWidgets.QSplashScreen(splash_pix, QtCore.Qt.WindowStaysOnTopHint)
    splash.show()
    time.sleep(2) 
    splash.close() 

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
