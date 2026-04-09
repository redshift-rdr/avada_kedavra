from burp import IBurpExtender, IHttpListener, ITab, IContextMenuFactory
from java.net import URL
from javax import swing
from java.awt import BorderLayout, FlowLayout, GridLayout
from java.io import PrintWriter
from javax.swing.table import DefaultTableModel
from javax.swing import JFileChooser, JFrame, JSplitPane, JTabbedPane, JTextArea
from javax.swing import BorderFactory, ListSelectionModel
from javax.swing.event import ListSelectionListener
import json

# from helpers import StupidAuthoriserController
# from ui.ui import UI

class BurpExtender(IBurpExtender, IHttpListener, ITab, IContextMenuFactory):
    def registerExtenderCallbacks(self, callbacks):
        callbacks.setExtensionName("Catcher")
        self._callbacks = callbacks
        self._helpers = callbacks.getHelpers()
        self.stdout = PrintWriter(self._callbacks.getStdout(), True)
        
        self.accumulator = []

        # self.controller = StupidAuthoriserController(self)
        # self.ui = UI(self)

        self.tab = swing.JPanel()
        self.tab.setLayout(BorderLayout())
        self._create_ui()
        #callbacks.registerContextMenuFactory(self.ui)
        callbacks.customizeUiComponent(self.tab)
        callbacks.addSuiteTab(self)
        callbacks.registerContextMenuFactory(self)

        # register ourselves as an HTTP listener
        callbacks.registerHttpListener(self)
        
        print('Loaded Catcher v0.01')
        return
    
    #
    # implement ITab
    #

    def getTabCaption(self):
        return 'CatcherInThePy'

    def getUiComponent(self):
        return self.tab
    
    #
    # implement ui
    #

    def _create_ui(self):
        # Create top control panel
        control_panel = swing.JPanel()
        control_panel.setLayout(BorderLayout())
        control_panel.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10))

        # Button panel (left side of control panel)
        button_panel = swing.JPanel()
        button_panel.setLayout(FlowLayout(FlowLayout.LEFT, 5, 0))
        self.remove_button = swing.JButton("Remove Requests", actionPerformed=self._btn_remove_pressed)
        self.save_button = swing.JButton("Save Requests to File", actionPerformed=self._btn_save_pressed)
        button_panel.add(self.remove_button)
        button_panel.add(self.save_button)

        # Add button panel to control panel
        control_panel.add(button_panel, BorderLayout.WEST)

        # Create filter panel with better organization
        filter_main_panel = swing.JPanel()
        filter_main_panel.setLayout(BorderLayout())
        filter_main_panel.setBorder(BorderFactory.createTitledBorder("Filters"))

        # Extension filter row
        ext_filter_panel = swing.JPanel()
        ext_filter_panel.setLayout(FlowLayout(FlowLayout.LEFT, 5, 5))
        self.filter_label = swing.JLabel("Extensions to ignore:")
        self.filter_input = swing.JTextField("js,gif,jpg,png,css,jpeg,ico,woff,woff2,svg", 35)
        ext_filter_panel.add(self.filter_label)
        ext_filter_panel.add(self.filter_input)

        # Method filter row
        method_filter_panel = swing.JPanel()
        method_filter_panel.setLayout(FlowLayout(FlowLayout.LEFT, 5, 5))
        method_label = swing.JLabel("Methods:")
        self.cb_get = swing.JCheckBox("GET", True)
        self.cb_post = swing.JCheckBox("POST", True)
        self.cb_put = swing.JCheckBox("PUT", True)
        self.cb_delete = swing.JCheckBox("DELETE", True)
        self.cb_other = swing.JCheckBox("Other", True)
        method_filter_panel.add(method_label)
        method_filter_panel.add(self.cb_get)
        method_filter_panel.add(self.cb_post)
        method_filter_panel.add(self.cb_put)
        method_filter_panel.add(self.cb_delete)
        method_filter_panel.add(self.cb_other)

        # Search filter row
        search_filter_panel = swing.JPanel()
        search_filter_panel.setLayout(FlowLayout(FlowLayout.LEFT, 5, 5))
        search_label = swing.JLabel("Search URL:")
        self.search_input = swing.JTextField(35)
        search_filter_panel.add(search_label)
        search_filter_panel.add(self.search_input)

        # Combine filter rows
        filter_rows_panel = swing.JPanel()
        filter_rows_panel.setLayout(GridLayout(3, 1, 5, 2))
        filter_rows_panel.add(ext_filter_panel)
        filter_rows_panel.add(method_filter_panel)
        filter_rows_panel.add(search_filter_panel)

        filter_main_panel.add(filter_rows_panel, BorderLayout.CENTER)
        control_panel.add(filter_main_panel, BorderLayout.EAST)

        # Create checkbox panel
        checkbox_panel = swing.JPanel()
        checkbox_panel.setLayout(FlowLayout(FlowLayout.LEFT, 10, 5))
        checkbox_panel.setBorder(BorderFactory.createEmptyBorder(0, 10, 5, 10))
        self.cb_collect = swing.JCheckBox("Collect in-scope proxied requests", True)
        self.table_label = swing.JLabel("Request Accumulator:")
        checkbox_panel.add(self.cb_collect)
        checkbox_panel.add(self.table_label)

        # Create top panel combining controls and checkbox
        top_panel = swing.JPanel()
        top_panel.setLayout(BorderLayout())
        top_panel.add(control_panel, BorderLayout.NORTH)
        top_panel.add(checkbox_panel, BorderLayout.SOUTH)

        # Create the table
        self.column_names = ("Index", "Method", "URL", "Params", )
        self.data_model = DefaultTableModel(None, self.column_names)
        self.table = swing.JTable(self.data_model)
        self.columnModel = self.table.getColumnModel()
        self.columnModel.getColumn(0).setPreferredWidth(50)
        self.columnModel.getColumn(1).setPreferredWidth(100)
        self.columnModel.getColumn(2).setPreferredWidth(800)
        self.columnModel.getColumn(3).setPreferredWidth(200)
        self.table.setAutoResizeMode(swing.JTable.AUTO_RESIZE_LAST_COLUMN)
        self.table.setSelectionMode(ListSelectionModel.SINGLE_SELECTION)
        self.table_scroll_pane = swing.JScrollPane(self.table)

        # Create details panel with tabs
        self._create_details_panel()

        # Add selection listener to table
        selection_model = self.table.getSelectionModel()
        selection_model.addListSelectionListener(TableSelectionListener(self))

        # Create split pane
        self.split_pane = JSplitPane(JSplitPane.VERTICAL_SPLIT, self.table_scroll_pane, self.details_panel)
        self.split_pane.setResizeWeight(0.6)
        self.split_pane.setDividerLocation(400)

        # Add components to main tab using BorderLayout
        self.tab.add(top_panel, BorderLayout.NORTH)
        self.tab.add(self.split_pane, BorderLayout.CENTER)

    def _create_details_panel(self):
        # Create tabbed pane for details
        self.details_tabs = JTabbedPane()

        # Request Info tab
        self.info_text = JTextArea()
        self.info_text.setEditable(False)
        self.info_text.setLineWrap(True)
        self.info_text.setWrapStyleWord(True)
        info_scroll = swing.JScrollPane(self.info_text)
        self.details_tabs.addTab("Request Info", info_scroll)

        # Headers tab
        self.headers_text = JTextArea()
        self.headers_text.setEditable(False)
        self.headers_text.setLineWrap(False)
        headers_scroll = swing.JScrollPane(self.headers_text)
        self.details_tabs.addTab("Headers", headers_scroll)

        # Parameters tab
        self.params_text = JTextArea()
        self.params_text.setEditable(False)
        self.params_text.setLineWrap(False)
        params_scroll = swing.JScrollPane(self.params_text)
        self.details_tabs.addTab("Parameters", params_scroll)

        # Create details panel
        self.details_panel = swing.JPanel()
        self.details_panel.setLayout(BorderLayout())
        self.details_panel.setBorder(BorderFactory.createTitledBorder("Request Details (select a row to view)"))
        self.details_panel.add(self.details_tabs, BorderLayout.CENTER)

    def _update_details_panel(self, index):
        if index < 0 or index >= len(self.accumulator):
            self._clear_details_panel()
            return

        request = self.accumulator[index]

        # Update info tab
        info_text = "URL: %s\n\n" % request['url']
        info_text += "Method: %s\n\n" % request['method']
        info_text += "Parameters: %d\n\n" % len(request['params'])
        info_text += "Hash Key: %s" % request['hashkey']
        self.info_text.setText(info_text)
        self.info_text.setCaretPosition(0)

        # Update headers tab
        headers_text = ""
        for header in request['headers']:
            headers_text += header + "\n"
        self.headers_text.setText(headers_text)
        self.headers_text.setCaretPosition(0)

        # Update parameters tab
        if request['params']:
            params_text = "%-30s | %-10s | %s\n" % ("Name", "Type", "Value")
            params_text += "-" * 80 + "\n"
            for param in request['params']:
                params_text += "%-30s | %-10s | %s\n" % (
                    param['name'][:30],
                    param['type'],
                    param['value'][:50]
                )
        else:
            params_text = "No parameters"
        self.params_text.setText(params_text)
        self.params_text.setCaretPosition(0)

    def _clear_details_panel(self):
        self.info_text.setText("Select a request to view details")
        self.headers_text.setText("")
        self.params_text.setText("")

    def addToAccumulator(self, request_json):
        # Check extension filter
        if self._filter_by_extension(request_json):
            return

        # Check method filter
        if self._filter_by_method(request_json):
            return

        # Check search filter
        if self._filter_by_search(request_json):
            return

        # Check scope
        if not self._callbacks.isInScope(URL(request_json['url'])):
            print(request_json['url'])
            return

        self.accumulator.append(request_json)
        self.data_model.addRow([len(self.accumulator)-1,request_json['method'],request_json['url'],len(request_json['params']),])

    def refreshTable(self):
        self.data_model.setRowCount(0)

        for i,request_json in enumerate(self.accumulator):
            self.data_model.addRow([i, request_json['method'],request_json['url'],len(request_json['params']), ])

    def _filter_by_extension(self, request):
        if not self.filter_input.getText():
            return False

        filters = self.filter_input.getText().split(',')
        request_extension = request['url'].split('.')[-1]

        if not request_extension:
            return False

        if request_extension in filters:
            return True

        return False

    def _filter_by_method(self, request):
        method = request['method'].upper()

        if method == 'GET' and not self.cb_get.isSelected():
            return True
        elif method == 'POST' and not self.cb_post.isSelected():
            return True
        elif method == 'PUT' and not self.cb_put.isSelected():
            return True
        elif method == 'DELETE' and not self.cb_delete.isSelected():
            return True
        elif method not in ['GET', 'POST', 'PUT', 'DELETE'] and not self.cb_other.isSelected():
            return True

        return False

    def _filter_by_search(self, request):
        search_term = self.search_input.getText().strip()

        if not search_term:
            return False

        # Case-insensitive search in URL
        if search_term.lower() not in request['url'].lower():
            return True

        return False

    def removeFromAccumulator(self, index_list):
        for index in reversed(index_list):
            del self.accumulator[index]

        self.refreshTable()

    def isInAccumulator(self, hashkey):
        for request in self.accumulator:
            if (hashkey == request['hashkey']):
                return True
            
        return False

    def saveAccumulator(self):
        frame = JFrame()
        fileChooser = JFileChooser()
        fileChooser.setDialogTitle("Specify a file to save")
        userSelection = fileChooser.showSaveDialog(frame)

        fileToSave = ''
        if (userSelection == JFileChooser.APPROVE_OPTION):
            fileToSave = fileChooser.getSelectedFile()
            
        frame.dispose()

        if not fileToSave:
            return
        
        f = open(str(fileToSave), 'w')
        f.write(json.dumps(self.accumulator))
        f.close()
        

    def _btn_remove_pressed(self, event):
        self.removeFromAccumulator(self.table.getSelectedRows())

    def _btn_save_pressed(self, event):
        self.saveAccumulator()

    def _hash_request(self, request_json):
        urlstr = request_json['url'].split('?')[0]
        headerstr = ''
        paramstr = ''

        # for header in request_json['headers']:
        #     headerstr += header.split(':')[0]

        for param in request_json['params']:
            paramstr += param['name']

        return hash(urlstr + headerstr + paramstr)

    #
    # implement IHttpListener
    #
    
    def processHttpMessage(self, toolFlag, messageIsRequest, messageInfo):
        # only process requests
        if not messageIsRequest:
            return
        
        if not self.cb_collect.isSelected():
            return

        request_json = self._message_to_json(messageInfo)
        
        if not self.isInAccumulator(request_json['hashkey']):
            self.addToAccumulator(request_json)

    def _message_to_json(self, message):
        # get the HTTP service for the request
        httpService = message.getHttpService()
        request = self._helpers.analyzeRequest(httpService, message.getRequest())
        method = request.getMethod()
        parameters = request.getParameters()
        url = request.getUrl()
        headers = list(request.getHeaders())

        request_json = {}
        request_json['url'] = str(url)
        request_json['method'] = method
        request_json['headers'] = headers
        request_json['params'] = self.parseParams(parameters)
        request_json['hashkey'] = self._hash_request(request_json)

        return request_json


    def parseParams(self, params):
        params_out = []
        for param in params:
            p = {}
            p['name'] = param.getName()
            p['value'] = param.getValue()

            if param.getType() == 0:
                p['type'] = 'url'
            elif param.getType() == 1:
                p['type'] = 'body'
            elif param.getType() == 2:
                p['type'] = 'cookie'
            elif param.getType() == 3:
                p['type'] = 'xml'
            elif param.getType() == 4:
                p['type'] = 'xml_attr'
            elif param.getType() == 5:
                p['type'] = 'multipart'
            elif param.getType() == 6:
                p['type'] = 'json'

            params_out.append(p)

        return params_out

    # Implement IContextMenuFactory
    def createMenuItems(self, invocation):
        menu = []
        ctx = invocation.getInvocationContext()

        if ctx in [0, 2, 4, 6]:
            menu.append(swing.JMenuItem("Add to Catcher", None, actionPerformed=lambda x, inv=invocation: self._ctx_menu_add(inv)))

        return menu if menu else None
    
    # called by createMenuItems
    def _ctx_menu_add(self, invocation):
        try:
            messages = invocation.getSelectedMessages()

            for message in messages:
                request_json = self._message_to_json(message)

                if not self.isInAccumulator(request_json['hashkey']):
                    self.addToAccumulator(request_json)
        except Exception as e:
            print('Failed to add request to Catcher: ', e)


# Table selection listener class
class TableSelectionListener(ListSelectionListener):
    def __init__(self, extender):
        self.extender = extender

    def valueChanged(self, e):
        if not e.getValueIsAdjusting():
            selected_row = self.extender.table.getSelectedRow()
            if selected_row >= 0:
                index = self.extender.table.getValueAt(selected_row, 0)
                self.extender._update_details_panel(index)
            else:
                self.extender._clear_details_panel()



