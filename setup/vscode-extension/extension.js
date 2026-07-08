// MCP Launcher — VS Code Sidebar Extension
// Provides a form to launch MCP Orchestrator jobs directly into Copilot Chat

'use strict';

const vscode = require('vscode');
const path   = require('path');
const fs     = require('fs');

// ── Static data ──────────────────────────────────────────────────────────────

const REPOS = ['cmpgn', 'uma', 'rvnu'];
const MODES = [
    { value: 'agent', label: 'Agent Mode' },
    { value: 'ask',   label: 'Ask Mode'   },
    { value: 'edit',  label: 'Edit Mode'  },
];

// Command format per agent (keyed by agent name; 'default' is fallback)
const COMMAND_FORMATS = {
    'mcp-orchestrator': (agent, job, repo) => `${agent} job_name=${job} repo=${repo}`,
    'Agent1':           (agent, job, repo) => `${agent} ${job}`,
    'Explore':          (agent, job)       => `${agent} ${job}`,
    'default':          (agent, job, repo) => `${agent} job_name=${job} repo=${repo}`,
};

// ── Agent discovery ───────────────────────────────────────────────────────────

/**
 * Read agent names from .github/agents/*.md files in the workspace.
 * Falls back to a hardcoded list if no files are found.
 */
function discoverAgents() {
    const fallback = ['mcp-orchestrator', 'Agent1', 'Explore'];
    const folders  = vscode.workspace.workspaceFolders;
    if (!folders) return fallback;

    for (const folder of folders) {
        const agentsDir = path.join(folder.uri.fsPath, '.github', 'agents');
        if (!fs.existsSync(agentsDir)) continue;
        try {
            const names = fs.readdirSync(agentsDir)
                .filter(f => f.endsWith('.md'))
                .map(f => {
                    // Try to extract 'name:' from YAML frontmatter
                    const content = fs.readFileSync(path.join(agentsDir, f), 'utf8');
                    const match   = content.match(/^name:\s*(.+)$/m);
                    return match ? match[1].trim() : path.basename(f, '.md');
                });
            if (names.length) return names;
        } catch { /* ignore read errors */ }
    }
    return fallback;
}

// ── Webview HTML ──────────────────────────────────────────────────────────────

function getHtml(agents, nonce) {
    const agentOpts = agents.map(a =>
        `<option value="${a}">${a}</option>`
    ).join('\n        ');

    const repoOpts = REPOS.map(r =>
        `<option value="${r}">${r.toUpperCase()}</option>`
    ).join('\n        ');

    const modeOpts = MODES.map(m =>
        `<option value="${m.value}">${m.label}</option>`
    ).join('\n        ');

    // Build the command-format map as a JS object for the webview
    const fmtMap = JSON.stringify(
        Object.fromEntries(
            Object.entries(COMMAND_FORMATS).map(([k, fn]) => [k, fn.toString()])
        )
    );

    return /* html */`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style nonce="${nonce}">
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    padding: 14px 12px 20px;
    font-family: var(--vscode-font-family);
    font-size: var(--vscode-font-size);
    color: var(--vscode-foreground);
    background: transparent;
    line-height: 1.4;
  }

  /* ── Header ── */
  .header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 18px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--vscode-sideBarSectionHeader-border,
                                var(--vscode-widget-border, #444));
  }
  .header-icon { font-size: 18px; line-height: 1; }
  .header-title {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--vscode-sideBarTitle-foreground, var(--vscode-foreground));
  }
  .header-sub {
    margin-left: auto;
    font-size: 10px;
    color: var(--vscode-descriptionForeground);
    opacity: 0.7;
  }

  /* ── Form fields ── */
  .field { margin-bottom: 13px; }

  label {
    display: block;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--vscode-descriptionForeground);
    margin-bottom: 5px;
  }

  select, input[type="text"] {
    width: 100%;
    padding: 5px 8px;
    background: var(--vscode-input-background);
    color: var(--vscode-input-foreground);
    border: 1px solid var(--vscode-input-border, var(--vscode-widget-border, #555));
    border-radius: 3px;
    font-family: var(--vscode-font-family);
    font-size: var(--vscode-font-size);
    outline: none;
    appearance: auto;
  }
  select:focus, input[type="text"]:focus {
    border-color: var(--vscode-focusBorder);
  }
  input[type="text"]::placeholder {
    color: var(--vscode-input-placeholderForeground);
    opacity: 0.7;
  }

  /* ── Divider ── */
  .divider {
    border: none;
    border-top: 1px solid var(--vscode-sideBarSectionHeader-border,
                              var(--vscode-widget-border, #444));
    margin: 16px 0;
  }

  /* ── Preview box ── */
  .preview-wrap {
    margin-bottom: 14px;
  }
  .preview-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--vscode-descriptionForeground);
    margin-bottom: 6px;
  }
  .preview-box {
    background: var(--vscode-textCodeBlock-background,
                    var(--vscode-editor-background));
    border: 1px solid var(--vscode-widget-border, #555);
    border-left: 3px solid var(--vscode-activityBarBadge-background,
                               var(--vscode-focusBorder, #007acc));
    border-radius: 3px;
    padding: 8px 10px;
    font-family: var(--vscode-editor-font-family, monospace);
    font-size: 11.5px;
    color: var(--vscode-textPreformat-foreground, var(--vscode-foreground));
    word-break: break-all;
    min-height: 34px;
    display: flex;
    align-items: center;
  }
  .preview-box.empty {
    color: var(--vscode-descriptionForeground);
    font-style: italic;
    font-size: 11px;
  }

  /* ── Buttons ── */
  .btn-row {
    display: flex;
    gap: 6px;
  }

  button {
    border: none;
    border-radius: 3px;
    font-family: var(--vscode-font-family);
    font-size: var(--vscode-font-size);
    cursor: pointer;
    padding: 6px 12px;
    font-weight: 600;
    transition: opacity 0.1s;
  }
  button:active { opacity: 0.8; }

  .btn-run {
    flex: 1;
    background: var(--vscode-button-background);
    color: var(--vscode-button-foreground);
  }
  .btn-run:hover:not(:disabled) {
    background: var(--vscode-button-hoverBackground);
  }
  .btn-run:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .btn-copy {
    flex: 0 0 auto;
    background: var(--vscode-button-secondaryBackground,
                    var(--vscode-button-background));
    color: var(--vscode-button-secondaryForeground,
                var(--vscode-button-foreground));
    padding: 6px 10px;
    opacity: 0.85;
  }
  .btn-copy:hover:not(:disabled) {
    background: var(--vscode-button-secondaryHoverBackground,
                    var(--vscode-button-hoverBackground));
    opacity: 1;
  }
  .btn-copy:disabled { opacity: 0.35; cursor: not-allowed; }

  /* ── Feedback flash ── */
  .feedback {
    margin-top: 10px;
    font-size: 11px;
    color: var(--vscode-notificationsInfoIcon-foreground,
                var(--vscode-foreground));
    min-height: 16px;
    text-align: center;
    opacity: 0;
    transition: opacity 0.2s;
  }
  .feedback.show { opacity: 1; }
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <span class="header-icon">🚀</span>
  <span class="header-title">MCP Orchestrator</span>
  <span class="header-sub">YOUR-ORG</span>
</div>

<!-- Repository -->
<div class="field">
  <label for="sel-repo">Repository</label>
  <select id="sel-repo">
    ${repoOpts}
  </select>
</div>

<!-- Agent -->
<div class="field">
  <label for="sel-agent">Agent</label>
  <select id="sel-agent">
    ${agentOpts}
  </select>
</div>

<!-- Mode -->
<div class="field">
  <label for="sel-mode">Chat Mode</label>
  <select id="sel-mode">
    ${modeOpts}
  </select>
</div>

<hr class="divider">

<!-- Job Name -->
<div class="field">
  <label for="inp-job">Job Name</label>
  <input type="text" id="inp-job"
         placeholder="e.g. scrng_frz_feat_fct_ddly"
         spellcheck="false" autocomplete="off" />
</div>

<!-- Preview -->
<div class="preview-wrap">
  <div class="preview-label">Command Preview</div>
  <div class="preview-box empty" id="preview">Enter a job name to preview</div>
</div>

<!-- Buttons -->
<div class="btn-row">
  <button class="btn-run" id="btn-run" disabled>▶&nbsp; Run in Copilot Chat</button>
  <button class="btn-copy" id="btn-copy" title="Copy command to clipboard" disabled>📋</button>
</div>

<div class="feedback" id="feedback"></div>

<script nonce="${nonce}">
  (function () {
    const vscode    = acquireVsCodeApi();
    const selRepo   = document.getElementById('sel-repo');
    const selAgent  = document.getElementById('sel-agent');
    const selMode   = document.getElementById('sel-mode');
    const inpJob    = document.getElementById('inp-job');
    const previewEl = document.getElementById('preview');
    const btnRun    = document.getElementById('btn-run');
    const btnCopy   = document.getElementById('btn-copy');
    const feedback  = document.getElementById('feedback');

    // Command-format functions injected from the extension
    const FORMATS = {
      'mcp-orchestrator': (agent, job, repo) => agent + ' job_name=' + job + ' repo=' + repo,
      'Agent1':           (agent, job)        => agent + ' ' + job,
      'Explore':          (agent, job)        => agent + ' ' + job,
    };
    function defaultFmt(agent, job, repo) { return agent + ' job_name=' + job + ' repo=' + repo; }

    function buildCommand() {
      const agent = selAgent.value;
      const repo  = selRepo.value;
      const job   = inpJob.value.trim();
      if (!job) return null;
      const fmt = FORMATS[agent] || defaultFmt;
      return fmt(agent, job, repo);
    }

    function update() {
      const cmd = buildCommand();
      if (cmd) {
        previewEl.textContent = cmd;
        previewEl.classList.remove('empty');
        btnRun.disabled  = false;
        btnCopy.disabled = false;
      } else {
        previewEl.textContent = 'Enter a job name to preview';
        previewEl.classList.add('empty');
        btnRun.disabled  = true;
        btnCopy.disabled = true;
      }
    }

    function flash(msg) {
      feedback.textContent = msg;
      feedback.classList.add('show');
      setTimeout(() => feedback.classList.remove('show'), 2500);
    }

    // Event listeners
    [selRepo, selAgent, selMode].forEach(el => el.addEventListener('change', update));
    inpJob.addEventListener('input', update);

    btnRun.addEventListener('click', () => {
      const cmd = buildCommand();
      if (!cmd) return;
      vscode.postMessage({ type: 'run', query: cmd, mode: selMode.value });
      flash('✓ Sent to Copilot Chat');
    });

    btnCopy.addEventListener('click', () => {
      const cmd = buildCommand();
      if (!cmd) return;
      vscode.postMessage({ type: 'copy', query: cmd });
    });

    // Handle messages from extension (e.g. copy confirmation)
    window.addEventListener('message', e => {
      if (e.data && e.data.type === 'copied') flash('✓ Copied to clipboard');
    });

    // Restore previous state (VS Code persists webview state across reloads)
    const prev = vscode.getState();
    if (prev) {
      if (prev.repo  && selRepo.querySelector('[value="' + prev.repo + '"]'))   selRepo.value  = prev.repo;
      if (prev.agent && selAgent.querySelector('[value="' + prev.agent + '"]')) selAgent.value = prev.agent;
      if (prev.mode  && selMode.querySelector('[value="' + prev.mode + '"]'))   selMode.value  = prev.mode;
      if (prev.job)  inpJob.value = prev.job;
    }
    update();

    // Persist state on any change
    function saveState() {
      vscode.setState({ repo: selRepo.value, agent: selAgent.value, mode: selMode.value, job: inpJob.value });
    }
    [selRepo, selAgent, selMode].forEach(el => el.addEventListener('change', saveState));
    inpJob.addEventListener('input', saveState);

  })();
</script>
</body>
</html>`;
}

// ── Webview Provider ──────────────────────────────────────────────────────────

class McpLauncherProvider {
    constructor(context) {
        this._context = context;
    }

    /** @param {vscode.WebviewView} webviewView */
    resolveWebviewView(webviewView) {
        const webview = webviewView.webview;

        webview.options = {
            enableScripts: true,
            localResourceRoots: [this._context.extensionUri],
        };

        const nonce  = getNonce();
        const agents = discoverAgents();
        webview.html = getHtml(agents, nonce);

        webview.onDidReceiveMessage(msg => {
            switch (msg.type) {
                case 'run':
                    // Open Copilot Chat panel and pre-fill the command
                    vscode.commands.executeCommand(
                        'workbench.action.chat.open',
                        { query: msg.query, mode: msg.mode }
                    );
                    break;

                case 'copy':
                    vscode.env.clipboard.writeText(msg.query).then(() => {
                        // Notify the webview so it can flash a confirmation
                        webview.postMessage({ type: 'copied' });
                    });
                    break;
            }
        });
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function getNonce() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let nonce = '';
    for (let i = 0; i < 32; i++) {
        nonce += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return nonce;
}

// ── Activation ────────────────────────────────────────────────────────────────

function activate(context) {
    const provider = new McpLauncherProvider(context);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('mcpLauncherView', provider, {
            webviewOptions: { retainContextWhenHidden: true },
        })
    );
}

function deactivate() {}

module.exports = { activate, deactivate };
