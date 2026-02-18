const vscode = require('vscode');
const path = require('path');
const { spawn } = require('child_process');
const { SetupWizard } = require('./setup_wizard');

let setupWizard = null;

async function activate(context) {
    console.log('Arduino Co-Pilot extension is now activating...');
    
    // Initialize setup wizard
    setupWizard = new SetupWizard(context);
    
    // Register setup command
    context.subscriptions.push(
        vscode.commands.registerCommand('arduino-co-pilot.runSetup', async () => {
            await setupWizard.runSetup();
        })
    );
    
    // Register the command to show the Co-Pilot panel
    context.subscriptions.push(
        vscode.commands.registerCommand('arduino-co-pilot.show', () => {
            CoPilotPanel.createOrShow(context, setupWizard);
        })
    );

    // Register the webview view provider for the Activity Bar
    try {
        const provider = new CoPilotViewProvider(context, setupWizard);
        context.subscriptions.push(
            vscode.window.registerWebviewViewProvider(
                'arduino-co-pilot-view', 
                provider,
                {
                    webviewOptions: {
                        retainContextWhenHidden: true
                    }
                }
            )
        );
        console.log('Arduino Co-Pilot webview provider registered successfully');
    } catch (error) {
        console.error('Failed to register Arduino Co-Pilot view provider:', error);
        vscode.window.showErrorMessage(`Arduino Co-Pilot activation failed: ${error.message}`);
    }
    
    // Skip auto setup check - user can trigger via command manually
    // Mark setup as complete since Python 3.10 + dependencies are already installed
    context.globalState.update('setupComplete', true);
}

// ── Helper: find the best Python executable ───────────────────────
function findPython() {
    const config = vscode.workspace.getConfiguration('arduino-co-pilot');
    const custom = config.get('pythonPath', '');
    if (custom) return custom;
    // Prefer system Python 3.10 where llama-cpp-python is installed
    const fs = require('fs');
    const sys310 = path.join(
        process.env.LOCALAPPDATA || '',
        'Programs', 'Python', 'Python310', 'python.exe'
    );
    if (fs.existsSync(sys310)) return sys310;
    return 'python';
}


// ── Helper: run the Python copilot_runner ──────────────────────────
function runCopilotRunner(extensionPath, prompt, callback) {
    const fs = require('fs');
    const devPath = 'C:\\Users\\sandeep.m.k\\Desktop\\Adrinuo-co-polit';
    
    // Find workspace: dev folder > global storage > extension path
    let workspaceFolder = extensionPath;
    
    if (fs.existsSync(path.join(devPath, 'Phi-3-mini-4k-instruct.Q4_0.gguf'))) {
        workspaceFolder = devPath;
    } else if (setupWizard) {
        const storagePath = setupWizard.getStoragePath();
        if (fs.existsSync(path.join(storagePath, 'Phi-3-mini-4k-instruct.Q4_0.gguf'))) {
            workspaceFolder = storagePath;
        }
    }
    
    // Find script: workspace folder > extension path
    let scriptPath = path.join(workspaceFolder, 'copilot_runner.py');
    if (!fs.existsSync(scriptPath)) {
        scriptPath = path.join(extensionPath, 'copilot_runner.py');
    }
    
    if (!fs.existsSync(scriptPath)) {
        callback(null, {
            code: `// Error: copilot_runner.py not found\n// Checked: ${workspaceFolder}\n// and: ${extensionPath}`,
            help: '', explanation: '', iot: '', rag_used: false, rag_docs: 0
        });
        return;
    }
    
    const pythonExe = findPython();
    console.log('Running copilot:', { scriptPath, workspaceFolder, pythonExe, prompt });
    
    const pythonProcess = spawn(pythonExe, [scriptPath, prompt, '--workspace', workspaceFolder]);

    let output = '';
    let errorOutput = '';

    pythonProcess.stdout.on('data', (data) => { output += data.toString(); });
    pythonProcess.stderr.on('data', (data) => { errorOutput += data.toString(); });

    pythonProcess.on('close', (code) => {
        console.log('Python process exited with code:', code);
        console.log('stdout length:', output.length);
        console.log('stderr length:', errorOutput.length);
        try {
            const jsonMatch = output.match(/\{[\s\S]*\}/);
            if (!jsonMatch) {
                throw new Error('No JSON found in output');
            }
            const result = JSON.parse(jsonMatch[0]);
            callback(null, result);
        } catch (err) {
            callback(null, {
                code: `// Error: ${err.message}\n// Python exit code: ${code}\n// stderr: ${errorOutput.substring(0, 500)}\n\n${output.substring(0, 500)}`,
                help: errorOutput || 'Could not generate output.',
                explanation: '',
                iot: '',
                rag_used: false,
                rag_docs: 0
            });
        }
    });

    pythonProcess.on('error', (err) => {
        console.error('Python spawn error:', err);
        callback(null, {
            code: `// Error spawning Python: ${err.message}\n// Python path: ${pythonExe}`,
            help: '', explanation: '', iot: '', rag_used: false, rag_docs: 0
        });
    });
}

// ── Shared HTML builder ────────────────────────────────────────────
function getWebviewHtml(isPanel) {
    const size = isPanel ? 'panel' : 'sidebar';
    const padding = isPanel ? '24px' : '16px';
    const titleSize = isPanel ? '24px' : '16px';
    const textareaHeight = isPanel ? '100px' : '80px';
    const fontSize = isPanel ? '14px' : '12px';
    const codeFontSize = isPanel ? '13px' : '11px';

    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Arduino Co-Pilot</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: ${padding};
            color: var(--vscode-foreground);
            background-color: ${isPanel ? 'var(--vscode-editor-background)' : 'var(--vscode-sideBar-background)'};
            line-height: 1.6;
            font-size: ${fontSize};
        }
        .header {
            display: flex; align-items: center; gap: 10px;
            margin-bottom: 16px; padding-bottom: 12px;
            border-bottom: 1px solid var(--vscode-panel-border);
        }
        .header h1, .header h2 { font-size: ${titleSize}; font-weight: 600; }
        .icon { font-size: ${isPanel ? '32px' : '24px'}; }

        /* Tabs */
        .tabs { display: flex; gap: 2px; margin-bottom: 12px; flex-wrap: wrap; }
        .tab {
            padding: 6px 12px; border: none; border-radius: 4px 4px 0 0;
            cursor: pointer; font-size: ${codeFontSize}; font-weight: 500;
            background: var(--vscode-tab-inactiveBackground);
            color: var(--vscode-tab-inactiveForeground);
            transition: background 0.2s;
        }
        .tab.active {
            background: var(--vscode-tab-activeBackground);
            color: var(--vscode-tab-activeForeground);
            border-bottom: 2px solid var(--vscode-focusBorder);
        }
        .tab:hover { background: var(--vscode-tab-hoverBackground); }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        /* Input */
        .input-section { margin-bottom: 16px; }
        .input-section label { display: block; margin-bottom: 6px; font-weight: 500; }
        textarea {
            width: 100%; min-height: ${textareaHeight}; padding: 10px;
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border: 1px solid var(--vscode-input-border);
            border-radius: 4px; font-family: 'Consolas', 'Monaco', monospace;
            font-size: ${codeFontSize}; resize: vertical;
        }
        textarea:focus { outline: none; border-color: var(--vscode-focusBorder); }

        /* Buttons */
        .btn-row { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
        .button-primary {
            flex: 1; background: var(--vscode-button-background);
            color: var(--vscode-button-foreground); border: none;
            padding: 8px 16px; border-radius: 4px; cursor: pointer;
            font-size: ${codeFontSize}; font-weight: 500;
        }
        .button-primary:hover { background: var(--vscode-button-hoverBackground); }
        .button-secondary {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            border: none; padding: 6px 12px; border-radius: 4px;
            cursor: pointer; font-size: ${codeFontSize};
        }
        .button-secondary:hover { background: var(--vscode-button-secondaryHoverBackground); }

        /* Results */
        .result-section {
            margin-bottom: 16px; border: 1px solid var(--vscode-panel-border);
            border-radius: 6px; overflow: hidden;
            background: var(--vscode-editor-background);
        }
        .result-header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 8px 12px; font-weight: 600; font-size: ${codeFontSize};
            background: var(--vscode-editorGroupHeader-tabsBackground);
            border-bottom: 1px solid var(--vscode-panel-border);
        }
        .result-content {
            padding: 12px; font-family: 'Consolas', 'Monaco', monospace;
            font-size: ${codeFontSize}; white-space: pre-wrap;
            overflow-x: auto; max-height: ${isPanel ? '500px' : '300px'}; overflow-y: auto;
        }
        .help-content, .explain-content, .iot-content {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.7; white-space: pre-wrap;
        }

        /* Status bar */
        .status-bar {
            display: flex; gap: 12px; align-items: center;
            padding: 6px 10px; margin-bottom: 12px; border-radius: 4px;
            background: var(--vscode-editorGroupHeader-tabsBackground);
            font-size: 11px; color: var(--vscode-descriptionForeground);
        }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
        .status-dot.green { background: #4caf50; }
        .status-dot.yellow { background: #ff9800; }
        .status-dot.red { background: #f44336; }

        /* Loader */
        .loader { text-align: center; padding: 32px; }
        .loader-spinner {
            width: 32px; height: 32px; margin: 0 auto 12px;
            border: 3px solid var(--vscode-panel-border);
            border-top-color: var(--vscode-button-background);
            border-radius: 50%; animation: spin 1s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .empty-state {
            text-align: center; padding: 40px 16px;
            color: var(--vscode-descriptionForeground);
        }
        .empty-state-icon { font-size: 36px; margin-bottom: 12px; opacity: 0.6; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="header">
        <div class="icon">🤖</div>
        ${isPanel ? '<h1>Arduino Co-Pilot</h1>' : '<h2>Arduino Co-Pilot</h2>'}
    </div>

    <div class="input-section">
        <label for="prompt-input">Describe your Arduino project:</label>
        <textarea id="prompt-input" placeholder="e.g., 'blink an LED on pin 13' or 'read DHT11 temperature sensor and display on LCD'"></textarea>
        <div class="btn-row">
            <button class="button-primary" onclick="generateCode()">✨ Generate Code</button>
        </div>
    </div>

    <div id="status-bar" class="status-bar hidden">
        <span><span class="status-dot" id="rag-dot"></span> RAG: <span id="rag-status">-</span></span>
        <span>Docs: <span id="rag-docs">0</span></span>
    </div>

    <div class="tabs hidden" id="result-tabs">
        <button class="tab active" onclick="switchTab('code')">📝 Code</button>
        <button class="tab" onclick="switchTab('connections')">🔌 Connections</button>
        <button class="tab" onclick="switchTab('explain')">📖 Explain</button>
        <button class="tab" onclick="switchTab('iot')">📡 IoT</button>
    </div>

    <div id="tab-code" class="tab-content active"></div>
    <div id="tab-connections" class="tab-content"></div>
    <div id="tab-explain" class="tab-content"></div>
    <div id="tab-iot" class="tab-content"></div>

    <div id="response">
        <div class="empty-state">
            <div class="empty-state-icon">💡</div>
            <p>Enter a description and click "Generate Code" to start!</p>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();

        function generateCode() {
            const prompt = document.getElementById('prompt-input').value.trim();
            if (!prompt) return;

            const responseDiv = document.getElementById('response');
            responseDiv.innerHTML = '<div class="loader"><div class="loader-spinner"></div><div>Generating Arduino code with RAG...</div></div>';

            document.getElementById('result-tabs').classList.add('hidden');
            document.getElementById('status-bar').classList.add('hidden');
            ['code','connections','explain','iot'].forEach(t => {
                document.getElementById('tab-' + t).innerHTML = '';
            });

            vscode.postMessage({ command: 'generate', prompt: prompt });
        }

        function switchTab(name) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + name).classList.add('active');
        }

        function copyToClipboard(text) {
            navigator.clipboard.writeText(text);
        }

        function insertCode(text) {
            vscode.postMessage({ command: 'insertCode', code: text });
        }

        function cleanMarkdown(text) {
            if (!text) return '';
            text = text.replace(/\\*\\*([^*]+)\\*\\*/g, '$1');
            text = text.replace(/\\*([^*]+)\\*/g, '$1');
            text = text.replace(new RegExp('^#{1,6}\\\\s+', 'gm'), '');
            text = text.replace(/\x60([^\x60]+)\x60/g, '$1');
            text = text.replace(new RegExp('\x60\x60\x60\\\\w*\\\\n?', 'g'), '');
            text = text.replace(/\x60\x60\x60/g, '');
            text = text.replace(new RegExp('^[\\\\-\\\\*]\\\\s+', 'gm'), String.fromCharCode(8226) + ' ');
            text = text.replace(new RegExp('\\\\n{3,}', 'g'), '\\n\\n');
            return text.trim();
        }

        window.addEventListener('message', event => {
            const msg = event.data;
            if (msg.command !== 'showResult') return;

            // Clean markdown from all text fields
            msg.help = cleanMarkdown(msg.help);
            msg.explanation = cleanMarkdown(msg.explanation);
            msg.iot = cleanMarkdown(msg.iot);

            const responseDiv = document.getElementById('response');
            responseDiv.innerHTML = '';

            // Status bar
            const statusBar = document.getElementById('status-bar');
            statusBar.classList.remove('hidden');
            const ragDot = document.getElementById('rag-dot');
            const ragStatus = document.getElementById('rag-status');
            const ragDocs = document.getElementById('rag-docs');
            if (msg.rag_used) {
                ragDot.className = 'status-dot green';
                ragStatus.textContent = 'Active';
                ragDocs.textContent = msg.rag_docs || 0;
            } else {
                ragDot.className = 'status-dot yellow';
                ragStatus.textContent = 'No index';
                ragDocs.textContent = '0';
            }

            // Show tabs
            document.getElementById('result-tabs').classList.remove('hidden');

            // Code tab
            const codeTab = document.getElementById('tab-code');
            codeTab.innerHTML = '';
            const codeSection = document.createElement('div');
            codeSection.className = 'result-section';
            codeSection.innerHTML =
                '<div class="result-header"><span>📝 Generated Arduino Code</span>' +
                '<div><button class="button-secondary" id="copy-btn">📋 Copy</button> ' +
                '<button class="button-secondary" id="insert-btn">⬇️ Insert</button></div></div>' +
                '<div class="result-content" id="code-content"></div>';
            codeSection.querySelector('#code-content').textContent = msg.code;
            codeSection.querySelector('#copy-btn').addEventListener('click', () => copyToClipboard(msg.code));
            codeSection.querySelector('#insert-btn').addEventListener('click', () => insertCode(msg.code));
            codeTab.appendChild(codeSection);

            // Connections tab
            const connTab = document.getElementById('tab-connections');
            connTab.innerHTML = '';
            if (msg.help) {
                const connSection = document.createElement('div');
                connSection.className = 'result-section';
                connSection.innerHTML =
                    '<div class="result-header"><span>🔌 Connection Instructions</span></div>' +
                    '<div class="result-content help-content" id="help-content"></div>';
                connSection.querySelector('#help-content').textContent = msg.help;
                connTab.appendChild(connSection);
            }

            // Explain tab (Tamil/English)
            const explainTab = document.getElementById('tab-explain');
            explainTab.innerHTML = '';
            if (msg.explanation) {
                const expSection = document.createElement('div');
                expSection.className = 'result-section';
                expSection.innerHTML =
                    '<div class="result-header"><span>📖 Why It Works (English / தமிழ்)</span></div>' +
                    '<div class="result-content explain-content" id="explain-content"></div>';
                expSection.querySelector('#explain-content').textContent = msg.explanation;
                explainTab.appendChild(expSection);
            } else {
                explainTab.innerHTML = '<div class="empty-state"><p>Explanation not available.</p></div>';
            }

            // IoT tab
            const iotTab = document.getElementById('tab-iot');
            iotTab.innerHTML = '';
            if (msg.iot) {
                const iotSection = document.createElement('div');
                iotSection.className = 'result-section';
                iotSection.innerHTML =
                    '<div class="result-header"><span>📡 MQTT & Node-RED Config</span>' +
                    '<button class="button-secondary" id="copy-iot-btn">📋 Copy</button></div>' +
                    '<div class="result-content iot-content" id="iot-content"></div>';
                iotSection.querySelector('#iot-content').textContent = msg.iot;
                iotSection.querySelector('#copy-iot-btn').addEventListener('click', () => copyToClipboard(msg.iot));
                iotTab.appendChild(iotSection);
            } else {
                iotTab.innerHTML = '<div class="empty-state"><p>IoT config not generated.</p></div>';
            }

            // Default to code tab
            switchTabDirect('code');
        });

        function switchTabDirect(name) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => {
                if (t.textContent.toLowerCase().includes(name === 'connections' ? 'connection' : name)) t.classList.add('active');
            });
            document.getElementById('tab-' + name).classList.add('active');
            // Fallback: activate first tab for code
            if (name === 'code') {
                document.querySelector('.tab').classList.add('active');
            }
        }

        document.getElementById('prompt-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                generateCode();
            }
        });
    </script>
</body>
</html>`;
}

// ── CoPilotPanel (full editor panel) ──────────────────────────────
class CoPilotPanel {
    static currentPanel = undefined;
    static viewType = 'coPilot';

    static createOrShow(context, setupWizardInstance) {
        const extensionPath = context.extensionPath;
        const column = vscode.window.activeTextEditor ? vscode.window.activeTextEditor.viewColumn : undefined;
        if (CoPilotPanel.currentPanel) {
            CoPilotPanel.currentPanel._panel.reveal(column);
            return;
        }
        const panel = vscode.window.createWebviewPanel(
            CoPilotPanel.viewType, 'Arduino Co-Pilot',
            column || vscode.ViewColumn.Two,
            { enableScripts: true, localResourceRoots: [vscode.Uri.file(path.join(extensionPath, 'media'))] }
        );
        CoPilotPanel.currentPanel = new CoPilotPanel(panel, extensionPath);
    }

    constructor(panel, extensionPath) {
        this._panel = panel;
        this._extensionPath = extensionPath;
        this._disposables = [];
        this._panel.webview.html = getWebviewHtml(true);
        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);
        this._panel.webview.onDidReceiveMessage(msg => this._handleMessage(msg), null, this._disposables);
    }

    _handleMessage(message) {
        console.log('Arduino Co-Pilot Panel: received message:', message.command);
        if (message.command === 'generate') {
            this._panel.webview.postMessage({ command: 'showLoading' });
            vscode.window.showInformationMessage('Arduino Co-Pilot: Generating code... (this may take 1-2 minutes)');
            console.log('Arduino Co-Pilot Panel: calling runCopilotRunner');
            runCopilotRunner(this._extensionPath, message.prompt, (err, result) => {
                console.log('Arduino Co-Pilot Panel: callback received, err:', err, 'hasResult:', !!result);
                if (err) {
                    this._panel.webview.postMessage({ command: 'showResult', code: `// Error: ${err.message}`, help: '', explanation: '', iot: '', rag_used: false, rag_docs: 0 });
                } else {
                    this._panel.webview.postMessage({ command: 'showResult', ...result });
                }
            });
        } else if (message.command === 'insertCode') {
            const editor = vscode.window.activeTextEditor;
            if (editor) {
                editor.edit(editBuilder => {
                    editBuilder.insert(editor.selection.active, message.code);
                });
            }
        }
    }

    dispose() {
        CoPilotPanel.currentPanel = undefined;
        this._panel.dispose();
        this._disposables.forEach(d => d.dispose());
    }
}

// ── CoPilotViewProvider (sidebar view) ────────────────────────────
class CoPilotViewProvider {
    constructor(context, setupWizardInstance) {
        this._context = context;
        this._extensionPath = context.extensionPath;
        this._setupWizard = setupWizardInstance;
    }

    resolveWebviewView(webviewView, context, _token) {
        this._view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [vscode.Uri.file(path.join(this._extensionPath, 'media'))]
        };
        webviewView.webview.html = getWebviewHtml(false);

        webviewView.webview.onDidReceiveMessage(msg => {
            console.log('Arduino Co-Pilot: received message:', msg.command);
            if (msg.command === 'generate') {
                vscode.window.showInformationMessage('Arduino Co-Pilot: Generating code... (this may take 1-2 minutes)');
                console.log('Arduino Co-Pilot: calling runCopilotRunner with prompt:', msg.prompt);
                runCopilotRunner(this._extensionPath, msg.prompt, (err, result) => {
                    console.log('Arduino Co-Pilot: callback received, err:', err, 'hasResult:', !!result);
                    if (err) {
                        webviewView.webview.postMessage({ command: 'showResult', code: `// Error: ${err.message}`, help: '', explanation: '', iot: '', rag_used: false, rag_docs: 0 });
                    } else {
                        webviewView.webview.postMessage({ command: 'showResult', ...result });
                    }
                });
            } else if (msg.command === 'insertCode') {
                const editor = vscode.window.activeTextEditor;
                if (editor) {
                    editor.edit(editBuilder => {
                        editBuilder.insert(editor.selection.active, msg.code);
                    });
                }
            }
        });
    }
}

function deactivate() {
    console.log('Arduino Co-Pilot extension is now deactivating...');
}

module.exports = { activate, deactivate };
