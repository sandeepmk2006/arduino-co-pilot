/**
 * First-run setup wizard for Arduino Co-Pilot
 * Handles Python detection, dependency installation, and model download
 */
const vscode = require('vscode');
const path = require('path');
const fs = require('fs');
const { spawn, exec } = require('child_process');
const https = require('https');

class SetupWizard {
    constructor(context) {
        this.context = context;
        this.globalStoragePath = context.globalStorageUri.fsPath;
        this.setupComplete = context.globalState.get('setupComplete', false);
    }

    async checkSetup() {
        if (this.setupComplete) {
            return true;
        }

        const result = await vscode.window.showWarningMessage(
            'Arduino Co-Pilot requires one-time setup. This will install Python dependencies and download the AI model (~2GB).',
            'Run Setup Now',
            'Cancel'
        );

        if (result === 'Run Setup Now') {
            return await this.runSetup();
        }
        return false;
    }

    async runSetup() {
        return await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: "Arduino Co-Pilot Setup",
            cancellable: true
        }, async (progress, token) => {
            try {
                // Step 1: Check Python
                progress.report({ increment: 10, message: "Checking Python installation..." });
                const pythonPath = await this.findOrInstallPython();
                if (!pythonPath) {
                    throw new Error('Python not found. Please install Python 3.10 or newer.');
                }

                // Step 2: Install dependencies
                progress.report({ increment: 20, message: "Installing Python dependencies..." });
                await this.installDependencies(pythonPath);

                // Step 3: Create storage directory
                progress.report({ increment: 10, message: "Creating storage directories..." });
                if (!fs.existsSync(this.globalStoragePath)) {
                    fs.mkdirSync(this.globalStoragePath, { recursive: true });
                }

                // Step 4: Copy bundled resources
                progress.report({ increment: 15, message: "Copying knowledge base..." });
                await this.copyBundledResources();

                // Step 5: Download or locate model
                progress.report({ increment: 20, message: "Setting up AI model..." });
                const modelPath = await this.setupModel(token);
                if (!modelPath) {
                    throw new Error('Model setup cancelled or failed.');
                }

                // Step 6: Test the setup
                progress.report({ increment: 15, message: "Testing installation..." });
                const testResult = await this.testSetup(pythonPath, modelPath);
                if (!testResult) {
                    throw new Error('Setup test failed. Please check console for errors.');
                }

                // Mark setup as complete
                progress.report({ increment: 10, message: "Setup complete!" });
                await this.context.globalState.update('setupComplete', true);
                await this.context.globalState.update('pythonPath', pythonPath);
                await this.context.globalState.update('modelPath', modelPath);
                this.setupComplete = true;

                vscode.window.showInformationMessage('Arduino Co-Pilot setup completed successfully!');
                return true;

            } catch (error) {
                vscode.window.showErrorMessage(`Setup failed: ${error.message}`);
                return false;
            }
        });
    }

    async findOrInstallPython() {
        // Try system Python 3.10
        const sys310 = path.join(
            process.env.LOCALAPPDATA || '',
            'Programs', 'Python', 'Python310', 'python.exe'
        );
        if (fs.existsSync(sys310)) {
            return sys310;
        }

        // Try python3 command
        try {
            const result = await this.execAsync('python --version');
            if (result.includes('Python 3.')) {
                return 'python';
            }
        } catch (e) {
            // Python not found
        }

        // Prompt user to install
        const result = await vscode.window.showErrorMessage(
            'Python 3.10+ is required but not found. Please install Python and restart VS Code.',
            'Download Python'
        );
        
        if (result === 'Download Python') {
            vscode.env.openExternal(vscode.Uri.parse('https://www.python.org/downloads/'));
        }
        
        return null;
    }

    async installDependencies(pythonPath) {
        const requirements = [
            'llama-cpp-python',
            'faiss-cpu',
            'sentence-transformers',
            'numpy',
            'beautifulsoup4',
            'requests'
        ];

        for (const pkg of requirements) {
            try {
                await this.execAsync(`"${pythonPath}" -m pip install ${pkg} --quiet`);
            } catch (error) {
                throw new Error(`Failed to install ${pkg}: ${error.message}`);
            }
        }
    }

    async copyBundledResources() {
        const extensionPath = this.context.extensionPath;
        const sources = ['scraper.py', 'vector_store.py', 'copilot_runner.py'];
        
        for (const file of sources) {
            const src = path.join(extensionPath, file);
            const dest = path.join(this.globalStoragePath, file);
            if (fs.existsSync(src)) {
                fs.copyFileSync(src, dest);
            }
        }

        // Copy docs_data if bundled
        const docsDataSrc = path.join(extensionPath, 'docs_data');
        const docsDataDest = path.join(this.globalStoragePath, 'docs_data');
        if (fs.existsSync(docsDataSrc)) {
            this.copyDirectory(docsDataSrc, docsDataDest);
        }
    }

    async setupModel(token) {
        // Check if model already exists in common locations
        const commonPaths = [
            'C:\\Users\\sandeep.m.k\\Desktop\\Adrinuo-co-polit\\Phi-3-mini-4k-instruct.Q4_0.gguf',
            path.join(this.globalStoragePath, 'Phi-3-mini-4k-instruct.Q4_0.gguf'),
            path.join(this.context.extensionPath, 'Phi-3-mini-4k-instruct.Q4_0.gguf')
        ];

        for (const p of commonPaths) {
            if (fs.existsSync(p)) {
                return p;
            }
        }

        // Prompt user for model location
        const choice = await vscode.window.showInformationMessage(
            'Phi-3 model file (2GB) not found. How would you like to proceed?',
            'Select Existing File',
            'Download Automatically',
            'Download Manually'
        );

        if (choice === 'Select Existing File') {
            const result = await vscode.window.showOpenDialog({
                canSelectFiles: true,
                canSelectFolders: false,
                filters: { 'GGUF Models': ['gguf'] },
                title: 'Select Phi-3-mini-4k-instruct.Q4_0.gguf'
            });
            return result ? result[0].fsPath : null;
        }

        if (choice === 'Download Manually') {
            vscode.window.showInformationMessage(
                'Download the model from: https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/blob/main/Phi-3-mini-4k-instruct-q4.gguf'
            );
            vscode.env.openExternal(vscode.Uri.parse('https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf'));
            return null;
        }

        // Auto-download would be implemented here (requires large file handling)
        vscode.window.showWarningMessage('Auto-download not yet implemented. Please select or manually download the model.');
        return null;
    }

    async testSetup(pythonPath, modelPath) {
        try {
            const testScript = path.join(this.globalStoragePath, 'copilot_runner.py');
            const workspace = this.globalStoragePath;
            
            const testCmd = `"${pythonPath}" "${testScript}" "test" --workspace "${workspace}" --no-explain --no-iot`;
            await this.execAsync(testCmd, { timeout: 30000 });
            return true;
        } catch (error) {
            console.error('Setup test failed:', error);
            return false;
        }
    }

    copyDirectory(src, dest) {
        if (!fs.existsSync(dest)) {
            fs.mkdirSync(dest, { recursive: true });
        }
        const entries = fs.readdirSync(src, { withFileTypes: true });
        for (const entry of entries) {
            const srcPath = path.join(src, entry.name);
            const destPath = path.join(dest, entry.name);
            if (entry.isDirectory()) {
                this.copyDirectory(srcPath, destPath);
            } else {
                fs.copyFileSync(srcPath, destPath);
            }
        }
    }

    execAsync(command, options = {}) {
        return new Promise((resolve, reject) => {
            exec(command, options, (error, stdout, stderr) => {
                if (error) {
                    reject(error);
                } else {
                    resolve(stdout);
                }
            });
        });
    }

    getStoragePath() {
        return this.globalStoragePath;
    }

    isSetupComplete() {
        return this.setupComplete;
    }
}

module.exports = { SetupWizard };
