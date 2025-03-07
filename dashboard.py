from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, QSizePolicy, 
                              QHBoxLayout, QScrollArea, QPushButton, QFileDialog)
from PySide6.QtCore import Qt, QTimer, QSize, QFileSystemWatcher
from PySide6.QtGui import QFont, QColor, QCursor
import sqlite3
import os
import csv
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# Constants
MARGIN = 16
SPACING = 16
SIDEBAR_MIN_WIDTH = 250
SIDEBAR_MAX_WIDTH = 400
CARD_MIN_WIDTH = 200
CARD_MAX_WIDTH = 280
CARD_MIN_HEIGHT = 100
CARD_MAX_HEIGHT = 130
GRAPH_MIN_HEIGHT = 150
GRAPH_MAX_HEIGHT = 300

class Dashboard(QWidget):
    def __init__(self, db_path, log_db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.log_db_path = log_db_path
        
        # Color scheme
        self.background_color = "#F7F9FC"
        self.card_background = "#FFFFFF"
        self.text_primary = "#2D3748"
        self.text_secondary = "#718096"
        self.shadow_color = "rgba(0,0,0,0.05)"
        self.accent_colors = {
            "total_products": "#4299E1",
            "total_stock": "#48BB78",
            "total_sales": "#ECC94B",
            "total_expenses": "#F56565",
            "net_profit": "#38B2AC",
            "damaged": "#ED8936",
            "top_product": "#9F7AEA",
            "avg_sale": "#319795",
            "profit_margin": "#ED64A6",
            "stock_turnover": "#667EEA"
        }
        
        self.setup_ui()
        self.load_data()
        self.setup_auto_refresh()

    def setup_auto_refresh(self):
        self.watcher = QFileSystemWatcher(self)
        self.watcher.addPath(self.db_path)
        self.watcher.addPath(self.log_db_path)
        self.watcher.fileChanged.connect(self.on_file_changed)
        self.fallback_timer = QTimer(self)
        self.fallback_timer.timeout.connect(self.check_and_refresh)
        self.fallback_timer.start(10000)

    def on_file_changed(self, path):
        if not os.path.exists(path):
            print(f"Warning: Watched file {path} no longer exists")
            return
        self.refresh()

    def check_and_refresh(self):
        self.refresh()

    def refresh(self):
        self.load_data()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        main_layout.setSpacing(SPACING)
        self.setStyleSheet(f"background-color: {self.background_color}; font-family: 'Roboto', sans-serif;")

        # Header
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_widget.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                stop:0 {self.accent_colors["total_products"]}, stop:1 {self.accent_colors["net_profit"]});
            border-radius: 10px;
            padding: 12px 20px;
            border: none;
        """)
        
        header_title = QLabel("PMS Dashboard")
        header_title.setStyleSheet("font-size: 22px; font-weight: 600; color: #FFFFFF; letter-spacing: 0.3px;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        
        refresh_button = QPushButton("Refresh")
        refresh_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: {self.accent_colors["total_products"]};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                border: 1px solid {self.accent_colors["total_products"]};
            }}
            QPushButton:hover {{
                background-color: {self._adjust_color(self.accent_colors["total_products"], -10)};
                color: #FFFFFF;
            }}
        """)
        refresh_button.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_button)
        
        export_button = QPushButton("Export Data")
        export_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: {self.accent_colors["net_profit"]};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                border: 1px solid {self.accent_colors["net_profit"]};
            }}
            QPushButton:hover {{
                background-color: {self._adjust_color(self.accent_colors["net_profit"], -10)};
                color: #FFFFFF;
            }}
        """)
        export_button.clicked.connect(self.export_data)
        header_layout.addWidget(export_button)
        
        main_layout.addWidget(header_widget)

        # Content layout
        content_layout = QHBoxLayout()
        content_layout.setSpacing(SPACING)
        main_layout.addLayout(content_layout)

        # Left content (metrics)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(SPACING)
        content_layout.addWidget(left_widget, stretch=7)

        # Metrics grid
        metrics_widget = QWidget()
        self.grid_layout = QGridLayout(metrics_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(SPACING)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.metrics = {
            "total_products": self.create_metric_card("Total Products", "0", self.accent_colors["total_products"], "Count of unique products in inventory"),
            "total_stock": self.create_metric_card("Total Stock", "0", self.accent_colors["total_stock"], "Total units currently in stock"),
            "total_sales": self.create_metric_card("Total Sales (NPR)", "0.00", self.accent_colors["total_sales"], "Cumulative revenue from sales"),
            "total_expenses": self.create_metric_card("Total Expenses (NPR)", "0.00", self.accent_colors["total_expenses"], "Cumulative operational costs"),
            "net_profit": self.create_metric_card("Net Profit (NPR)", "0.00", self.accent_colors["net_profit"], "Profit after expenses"),
            "damaged": self.create_metric_card("Damaged Products", "0", self.accent_colors["damaged"], "Total unreplaced damaged items"),
            "top_product": self.create_metric_card("Top Product", "N/A", self.accent_colors["top_product"], "Product with highest sales quantity"),
            "avg_sale": self.create_metric_card("Avg Sale Value (NPR)", "0.00", self.accent_colors["avg_sale"], "Average revenue per transaction"),
            "profit_margin": self.create_metric_card("Profit Margin (%)", "0.00", self.accent_colors["profit_margin"], "Net profit as a percentage of total sales"),
            "stock_turnover": self.create_metric_card("Stock Turnover", "0.00", self.accent_colors["stock_turnover"], "Rate of stock sold and replaced")
        }

        self.update_grid_layout()
        left_layout.addWidget(metrics_widget)

        # Summary widget
        summary_widget = QWidget()
        summary_layout = QHBoxLayout(summary_widget)
        summary_widget.setStyleSheet(f"""
            background-color: {self.card_background};
            border-radius: 10px;
            border: 1px solid #E2E8F0;
            box-shadow: 0 3px 5px {self.shadow_color};
            padding: 12px;
        """)
        self.summary_label = QLabel("Revenue: 0.00 NPR | Expenses: 0.00 NPR")
        self.summary_label.setStyleSheet(f"color: {self.text_primary}; font-size: 14px; font-weight: 500;")
        summary_layout.addWidget(self.summary_label)
        left_layout.addWidget(summary_widget)

        # Low Stock Alerts
        self.low_stock_box = QWidget()
        self.low_stock_box.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 {self.card_background}, stop:1 {self._adjust_color(self.accent_colors["damaged"], 50)});
            border-radius: 12px;
            border: none;
            box-shadow: 0 4px 8px {self.shadow_color};
        """)
        self.low_stock_layout = QVBoxLayout(self.low_stock_box)
        self.low_stock_layout.setContentsMargins(12, 12, 12, 12)
        self.low_stock_layout.setSpacing(8)
        
        low_stock_title = QLabel("Low Stock Alerts")
        low_stock_title.setStyleSheet(f"""
            font-size: 16px; 
            font-weight: 600; 
            color: {self.accent_colors["damaged"]};
            padding: 6px 12px;
            background-color: transparent;
            border-radius: 6px;
        """)
        low_stock_title.setAlignment(Qt.AlignCenter)
        self.low_stock_layout.addWidget(low_stock_title)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.low_stock_box)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {self.card_background};
                width: 8px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {self.text_secondary};
                border-radius: 4px;
            }}
        """)
        left_layout.addWidget(self.scroll_area)
        left_layout.addStretch()

        # Right sidebar
        sidebar_widget = QWidget()
        self.sidebar_layout = QVBoxLayout(sidebar_widget)
        self.sidebar_layout.setContentsMargins(MARGIN, 12, 12, 12)
        self.sidebar_layout.setSpacing(SPACING)
        sidebar_widget.setStyleSheet(f"""
            background-color: {self.card_background};
            border-radius: 12px;
            border: none;
            box-shadow: 0 4px 8px {self.shadow_color};
        """)
        sidebar_widget.setMaximumWidth(SIDEBAR_MAX_WIDTH)
        sidebar_widget.setMinimumWidth(SIDEBAR_MIN_WIDTH)
        content_layout.addWidget(sidebar_widget, stretch=3)

        # Top 5 Selling Products Graph
        top_products_container = QWidget()
        top_products_layout = QVBoxLayout(top_products_container)
        top_products_layout.setContentsMargins(12, 12, 12, 12)
        top_products_layout.setSpacing(8)
        top_products_container.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 {self.card_background}, stop:1 {self._adjust_color(self.accent_colors["total_products"], 50)});
            border-radius: 12px;
            border: none;
            box-shadow: 0 4px 8px {self.shadow_color};
        """)
        
        top_products_title = QLabel("Top 5 Selling Products")
        top_products_title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {self.accent_colors['total_products']};")
        top_products_title.setAlignment(Qt.AlignCenter)
        top_products_layout.addWidget(top_products_title)

        self.top_products_fig = plt.Figure(dpi=100)
        self.top_products_canvas = FigureCanvas(self.top_products_fig)
        self.top_products_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        top_products_layout.addWidget(self.top_products_canvas)
        self.sidebar_layout.addWidget(top_products_container)

        # Stock Available Graph
        stock_container = QWidget()
        stock_layout = QVBoxLayout(stock_container)
        stock_layout.setContentsMargins(12, 12, 12, 12)
        stock_layout.setSpacing(8)
        stock_container.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 {self.card_background}, stop:1 {self._adjust_color(self.accent_colors["total_stock"], 50)});
            border-radius: 12px;
            border: none;
            box-shadow: 0 4px 8px {self.shadow_color};
        """)
        
        stock_title = QLabel("Stock Available")
        stock_title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {self.accent_colors['total_stock']};")
        stock_title.setAlignment(Qt.AlignCenter)
        stock_layout.addWidget(stock_title)

        self.stock_fig = plt.Figure(dpi=100)
        self.stock_canvas = FigureCanvas(self.stock_fig)
        self.stock_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        stock_layout.addWidget(self.stock_canvas)
        self.sidebar_layout.addWidget(stock_container)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_grid_layout()
        graph_height = max(GRAPH_MIN_HEIGHT, min(GRAPH_MAX_HEIGHT, int(self.height() * 0.3)))
        self.top_products_canvas.setFixedHeight(graph_height)
        self.stock_canvas.setFixedHeight(graph_height)
        
        # Responsive low stock scroll area
        scroll_height = max(100, min(300, int(self.height() * 0.25)))
        self.scroll_area.setMaximumHeight(scroll_height)

    def update_grid_layout(self):
        for i in reversed(range(self.grid_layout.count())):
            self.grid_layout.takeAt(i).widget().setParent(None)
        if self.width() < 800:
            for i, (key, widget) in enumerate(self.metrics.items()):
                self.grid_layout.addWidget(widget, i // 2, i % 2)  # 2 columns on narrow screens
        else:
            positions = [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2), (1, 3), (2, 0), (2, 1)]
            for (row, col), (key, widget) in zip(positions, self.metrics.items()):
                self.grid_layout.addWidget(widget, row, col)

    def _adjust_color(self, color, amount):
        try:
            c = QColor(color)
            r, g, b, a = c.red(), c.green(), c.blue(), c.alpha()
            r = min(255, max(0, r + amount))
            g = min(255, max(0, g + amount))
            b = min(255, max(0, b + amount))
            return QColor(r, g, b, a).name()
        except Exception as e:
            print(f"Error adjusting color: {e}")
            return color

    def create_metric_card(self, title, value, color, tooltip):
        card = QWidget()
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)
        card.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 {self.card_background}, stop:1 {self._adjust_color(color, 50)});
            border-radius: 12px;
            border: none;
            box-shadow: 0 4px 8px {self.shadow_color};
            transition: all 0.2s;
        """)
        card.setMinimumSize(CARD_MIN_WIDTH, CARD_MIN_HEIGHT)
        card.setMaximumSize(CARD_MAX_WIDTH, CARD_MAX_HEIGHT)
        card.setToolTip(tooltip)
        card.setCursor(QCursor(Qt.PointingHandCursor))
        card.enterEvent = lambda e: card.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 {self.card_background}, stop:1 {self._adjust_color(color, 40)});
            border-radius: 12px;
            border: none;
            box-shadow: 0 6px 12px {self.shadow_color};
            transform: translateY(-2px);
        """)
        card.leaveEvent = lambda e: card.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 {self.card_background}, stop:1 {self._adjust_color(color, 50)});
            border-radius: 12px;
            border: none;
            box-shadow: 0 4px 8px {self.shadow_color};
        """)

        color_bar = QWidget()
        color_bar.setStyleSheet(f"background-color: {color}; border-radius: 4px;")
        color_bar.setFixedWidth(6)
        card_layout.addWidget(color_bar)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {self.text_secondary}; font-size: 13px; font-weight: 500;")
        text_layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {self.text_primary}; font-size: 22px; font-weight: 700;")
        text_layout.addWidget(value_label)

        card_layout.addLayout(text_layout)
        card_layout.addStretch()

        return card

    def export_data(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Data", "", "CSV Files (*.csv)")
        if not file_path:
            return
        try:
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Metric", "Value"])
                for key, widget in self.metrics.items():
                    value = widget.layout().itemAt(1).layout().itemAt(1).widget().text()
                    writer.writerow([key.replace('_', ' ').title(), value])
                
                writer.writerow([])
                writer.writerow(["Low Stock Alerts"])
                writer.writerow(["Product", "Stock", "Urgency"])
                for i in range(1, self.low_stock_layout.count()):
                    item = self.low_stock_layout.itemAt(i)
                    if item and item.widget():
                        text = item.widget().text()
                        if "No low stock items" not in text and "Error" not in text:
                            name_stock, urgency = text.split(" (")
                            name, stock = name_stock.split(": ")
                            writer.writerow([name, stock.split()[0], urgency[:-1]])
        except Exception as e:
            print(f"Error exporting data: {e}")

    def update_top_products_chart(self):
        ax = self.top_products_fig.gca() or self.top_products_fig.add_subplot(111)
        ax.clear()
        ax.set_facecolor(self.card_background)
        try:
            with sqlite3.connect(self.log_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT item, SUM(quantity) FROM daily_accessories_sales GROUP BY item ORDER BY SUM(quantity) DESC LIMIT 5")
                data = cursor.fetchall()
            products, quantities = zip(*data) if data else (["No Data"], [0])
            ax.bar(products, quantities, color=self.accent_colors["total_products"])
            ax.set_title("Top 5 Selling Products", fontsize=12, fontweight='500', color=self.text_primary)
            ax.set_ylabel("Units Sold", fontsize=10, fontweight='500', color=self.text_secondary)
            ax.tick_params(axis='x', rotation=45, labelsize=8, colors=self.text_primary)
            ax.tick_params(axis='y', labelsize=8, colors=self.text_secondary)
            self.top_products_fig.tight_layout()
        except sqlite3.Error as e:
            print(f"Error in update_top_products_chart: {e}")
            ax.text(0.5, 0.5, "Error Loading Data", ha='center', va='center', fontsize=10, color=self.accent_colors["total_expenses"])
        self.top_products_canvas.draw()

    def update_stock_chart(self):
        ax = self.stock_fig.gca() or self.stock_fig.add_subplot(111)
        ax.clear()
        ax.set_facecolor(self.card_background)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name, stock FROM products ORDER BY stock DESC LIMIT 5")
                data = cursor.fetchall()
            products, stocks = zip(*data) if data else (["No Data"], [0])
            ax.bar(products, stocks, color=self.accent_colors["total_stock"])
            ax.set_title("Stock Available", fontsize=12, fontweight='500', color=self.text_primary)
            ax.set_ylabel("Units", fontsize=10, fontweight='500', color=self.text_secondary)
            ax.tick_params(axis='x', rotation=45, labelsize=8, colors=self.text_primary)
            ax.tick_params(axis='y', labelsize=8, colors=self.text_secondary)
            self.stock_fig.tight_layout()
        except sqlite3.Error as e:
            print(f"Error in update_stock_chart: {e}")
            ax.text(0.5, 0.5, "Error Loading Data", ha='center', va='center', fontsize=10, color=self.accent_colors["total_expenses"])
        self.stock_canvas.draw()

    def update_low_stock_alerts(self):
        for i in reversed(range(self.low_stock_layout.count())):
            if i > 0:
                item = self.low_stock_layout.itemAt(i)
                if item and item.widget():
                    item.widget().deleteLater()

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name, stock FROM products WHERE stock < 5 ORDER BY stock ASC")
                low_stock_items = cursor.fetchall()
            
            if low_stock_items:
                for name, stock in low_stock_items:
                    if stock == 0:
                        bg_color = "#FFF5F5"
                        text_color = "#F56565"
                        urgency = "Critical"
                    elif stock <= 2:
                        bg_color = "#FEF7F7"
                        text_color = "#ED8936"
                        urgency = "Urgent"
                    else:
                        bg_color = "#F7FAFC"
                        text_color = "#ECC94B"
                        urgency = "Low"
                    
                    alert_label = QLabel(f"{name}: {stock} units ({urgency})")
                    alert_label.setStyleSheet(f"""
                        background-color: {bg_color};
                        color: {text_color};
                        font-size: 13px;
                        font-weight: 500;
                        padding: 6px 12px;
                        border-radius: 6px;
                        margin: 2px 0;
                        border-left: 3px solid {text_color};
                    """)
                    alert_label.setToolTip(f"Stock level: {stock} units - {urgency} priority")
                    self.low_stock_layout.addWidget(alert_label)
            else:
                no_alert_label = QLabel("No low stock items")
                no_alert_label.setStyleSheet(f"""
                    color: {self.text_secondary}; 
                    font-size: 13px; 
                    padding: 6px 12px;
                    font-style: italic;
                    background-color: #EDF2F7;
                    border-radius: 6px;
                """)
                self.low_stock_layout.addWidget(no_alert_label)
        except sqlite3.Error as e:
            print(f"Error in update_low_stock_alerts: {e}")
            error_label = QLabel("Error Loading Alerts")
            error_label.setStyleSheet(f"""
                color: {self.accent_colors['total_expenses']}; 
                font-size: 13px; 
                padding: 6px 12px;
                background-color: #FFF5F5;
                border-radius: 6px;
            """)
            self.low_stock_layout.addWidget(error_label)
        
        self.low_stock_layout.addStretch()

    def table_exists(self, conn, table_name):
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            return cursor.fetchone() is not None
        except sqlite3.Error as e:
            print(f"Error checking table existence: {e}")
            return False

    def load_data(self):
        try:
            if not os.path.exists(self.db_path) or not os.path.exists(self.log_db_path):
                raise sqlite3.OperationalError(f"Database file not found: {self.db_path}, {self.log_db_path}")
            
            with sqlite3.connect(self.db_path) as products_conn, sqlite3.connect(self.log_db_path) as log_conn:
                if not self.table_exists(products_conn, "products") or not self.table_exists(log_conn, "daily_accessories_sales"):
                    raise sqlite3.OperationalError("Required tables missing")

                cursor = products_conn.cursor()
                log_cursor = log_conn.cursor()

                cursor.execute("SELECT COUNT(*) as total_products, SUM(stock) as total_stock FROM products")
                total_products, total_stock = cursor.fetchone()
                total_stock = total_stock or 0
                self.metrics["total_products"].layout().itemAt(1).layout().itemAt(1).widget().setText(str(total_products))
                self.metrics["total_stock"].layout().itemAt(1).layout().itemAt(1).widget().setText(str(total_stock))

                log_cursor.execute("SELECT SUM(total) as total_sales, AVG(total) as avg_sale, SUM(quantity) as total_quantity FROM daily_accessories_sales")
                sales_data = log_cursor.fetchone()
                total_sales = sales_data[0] or 0
                avg_sale = sales_data[1] or 0
                total_sales_quantity = sales_data[2] or 0
                self.metrics["total_sales"].layout().itemAt(1).layout().itemAt(1).widget().setText(f"{total_sales:,.2f}")
                self.metrics["avg_sale"].layout().itemAt(1).layout().itemAt(1).widget().setText(f"{avg_sale:,.2f}")

                total_expenses = 0
                if self.table_exists(log_conn, "expenses"):
                    log_cursor.execute("SELECT SUM(amount) FROM expenses")
                    total_expenses = log_cursor.fetchone()[0] or 0
                self.metrics["total_expenses"].layout().itemAt(1).layout().itemAt(1).widget().setText(f"{total_expenses:,.2f}")

                profit_total = expense_total = 0
                if self.table_exists(log_conn, "bank_transactions"):
                    log_cursor.execute("SELECT SUM(amount) FROM bank_transactions WHERE type='profit'")
                    profit_total = log_cursor.fetchone()[0] or 0
                    log_cursor.execute("SELECT SUM(amount) FROM bank_transactions WHERE type='expense'")
                    expense_total = abs(log_cursor.fetchone()[0] or 0)
                net_profit = profit_total - expense_total
                self.metrics["net_profit"].layout().itemAt(1).layout().itemAt(1).widget().setText(f"{net_profit:,.2f}")

                top_product_name = "N/A"
                top_quantity = 0
                if self.table_exists(log_conn, "daily_accessories_sales"):
                    log_cursor.execute("SELECT item, SUM(quantity) FROM daily_accessories_sales GROUP BY item ORDER BY SUM(quantity) DESC LIMIT 1")
                    top_product = log_cursor.fetchone()
                    if top_product:
                        top_product_name, top_quantity = top_product
                        self.metrics["top_product"].setToolTip(f"Top Product: {top_product_name}\nQuantity Sold: {top_quantity}")
                self.metrics["top_product"].layout().itemAt(1).layout().itemAt(1).widget().setText(top_product_name)

                total_damaged = 0
                if self.table_exists(log_conn, "damaged_products"):
                    log_cursor.execute("SELECT SUM(quantity) FROM damaged_products WHERE replaced = 0")
                    total_damaged = log_cursor.fetchone()[0] or 0
                self.metrics["damaged"].layout().itemAt(1).layout().itemAt(1).widget().setText(str(total_damaged))

                profit_margin = (net_profit / total_sales * 100) if total_sales else 0
                self.metrics["profit_margin"].layout().itemAt(1).layout().itemAt(1).widget().setText(f"{profit_margin:,.2f}")
                self.metrics["profit_margin"].setToolTip(f"Profit Margin: {profit_margin:,.2f}%\nNet Profit: {net_profit:,.2f} NPR\nTotal Sales: {total_sales:,.2f} NPR")

                stock_turnover = (total_sales_quantity / total_stock) if total_stock else 0
                self.metrics["stock_turnover"].layout().itemAt(1).layout().itemAt(1).widget().setText(f"{stock_turnover:,.2f}")
                self.metrics["stock_turnover"].setToolTip(f"Stock Turnover: {stock_turnover:,.2f}\nSales Quantity: {total_sales_quantity}\nAverage Stock: {total_stock}")

                self.summary_label.setText(f"Revenue: {total_sales:,.2f} NPR | Expenses: {total_expenses:,.2f} NPR")

        except sqlite3.OperationalError as e:
            print(f"Database error in dashboard: {e}")
            self.reset_metrics()
        except Exception as e:
            print(f"Unexpected error in load_data: {e}")
            self.reset_metrics()

        self.update_top_products_chart()
        self.update_stock_chart()
        self.update_low_stock_alerts()

    def reset_metrics(self):
        for key in self.metrics:
            default_value = "0" if key != "top_product" else "N/A"
            self.metrics[key].layout().itemAt(1).layout().itemAt(1).widget().setText(default_value)
        self.summary_label.setText("Revenue: 0.00 NPR | Expenses: 0.00 NPR")

    def closeEvent(self, event):
        self.watcher.fileChanged.disconnect(self.on_file_changed)
        self.fallback_timer.stop()
        self.top_products_fig.clear()
        self.stock_fig.clear()
        event.accept()

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    dashboard = Dashboard("products.db", "logs.db")
    dashboard.show()
    sys.exit(app.exec())