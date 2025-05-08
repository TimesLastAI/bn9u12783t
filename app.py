<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="theme-color" content="#27272a">
  <!-- *** MODIFICATION 1: Added viewport-fit=cover *** -->
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <title>AI Chat</title>
  <style>
    /* Theme variables - DARK THEME (Purple Accent) */
    :root {
      --body-bg: #18181b;
      --bg: #202024;
      --header-bg: #27272a;
      --input-bg: #3f3f46; /* Used for input bg, buttons */
      --bubble-user: #3f3f46; /* User bubble GRAY */
      --bubble-user-text: #e4e4e7; /* User bubble text */
      --bubble-assistant-text: #e4e4e7;
      --bubble-error-bg: #581c1c;
      --bubble-error-border: #f87171;
      --bubble-error-text: #fca5a5;
      --bubble-file-bg: #4b5563; /* Used for file block in user message AND preview */
      --bubble-file-text: #e4e4e7;
      --bubble-file-info-text: #a1a1aa;
      --text: #e4e4e7;
      --text-muted: #a1a1aa;
      --accent: #8b5cf6; /* Purple accent */
      --input-border: #52525b;
      --input-border-focus: var(--accent);
      --button-disabled-bg: #52525b;
      --send-button-bg: var(--accent);
      --send-button-hover-bg: #7c3aed;
      --send-button-icon: #ffffff;
      --scrollbar-thumb: #52525b;
      --scrollbar-thumb-hover: #71717a;
      --spinner-border: #52525b;
      --spinner-top: var(--accent);
      --textarea-scrollbar-thumb: #52525b; /* Custom scrollbar for textarea */
      --textarea-scrollbar-track: var(--body-bg); /* Match input background */

      --sidebar-width: 260px;
      --sidebar-bg: var(--body-bg);
      --sidebar-border: var(--input-bg);
      --conversation-hover-bg: var(--input-bg);
    }

    /* Reset & base */
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html { height: 100%; }
    body {
      background: var(--body-bg);
      color: var(--text);
      font-family: 'Segoe UI', Tahoma, sans-serif;
      display: flex;
      height: 100vh;
      overflow: hidden; /* Prevent body scroll */
    }

    /* --- Sidebar --- */
    #sidebar {
      width: 0;
      background: var(--sidebar-bg);
      border-right: 1px solid var(--sidebar-border);
      display: flex;
      flex-direction: column;
      transition: width 0.3s ease;
      z-index: 30;
      flex-shrink: 0;
      overflow: hidden;
      height: 100%; /* Ensure full height */
    }
    #sidebar.open {
      width: var(--sidebar-width);
    }
    .sidebar-header {
       padding: 10px;
       border-bottom: 1px solid var(--sidebar-border);
       display: flex;
       align-items: center;
       justify-content: flex-end;
       height: 55px; /* Match header height */
       flex-shrink: 0;
    }
    #sidebarCloseBtn {
       background: transparent; border: none; color: var(--text-muted);
       border-radius: 50%; width: 32px; height: 32px;
       display: flex; align-items: center; justify-content: center;
       cursor: pointer; transition: background-color 0.2s, color 0.2s; padding: 0;
    }
    #sidebarCloseBtn:hover { background-color: var(--input-bg); color: var(--text); }
    .sidebar-close-icon { width: 18px; height: 18px; display: block; }
    .sidebar-content {
       flex-grow: 1; overflow-y: auto; padding: 0;
    }
    .sidebar-content::-webkit-scrollbar { width: 6px; }
    .sidebar-content::-webkit-scrollbar-track { background: transparent; }
    .sidebar-content::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 3px; }
    .sidebar-content::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-thumb-hover); }

    #conversationsList { padding: 10px 0; }
    .conversation-item {
      padding: 10px 15px; cursor: pointer; color: var(--text-muted);
      font-size: 14px; border-bottom: 1px solid var(--sidebar-border);
      transition: background .2s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .conversation-item:last-child { border-bottom: none; }
    .conversation-item:hover, .conversation-item.active { background: var(--conversation-hover-bg); color: var(--text); }
    .conversation-item .conv-title { display: block; font-weight: 500; color: var(--text); margin-bottom: 3px;}
    .conversation-item .conv-date { font-size: 11px; }

    /* --- Main Content Area --- */
    #main {
      flex-grow: 1; display: flex; flex-direction: column;
      height: 100vh; overflow: hidden; /* Prevent scroll here, handled by wrapper */
      transition: margin-left 0.3s ease; position: relative;
    }

    /* Header */
    .header {
      background: var(--header-bg); padding: 0 16px;
      display: flex; justify-content: space-between; align-items: center;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1); /* Softer shadow */
      position: relative; z-index: 20; flex-shrink: 0; height: 55px;
      border-bottom: 1px solid var(--input-border);
    }
    .header .left-controls { display: flex; gap: 10px; align-items: center; }
    .header button {
      background: transparent; border: none; color: var(--text-muted);
      padding: 8px 12px; border-radius: 6px; cursor: pointer;
      transition: background .2s, color .2s; font-size: 14px;
      display: flex; align-items: center; gap: 6px;
    }
    .header button:hover { background: var(--input-bg); color: var(--text); }
    .sidebar-toggle-btn { padding: 8px; color: var(--accent); }
    .sidebar-toggle-btn:hover { background: var(--input-bg); color: var(--send-button-hover-bg); }
    .header-icon { font-size: 20px; width: 20px; height: 20px; display: block; }

    /* Messages area */
    .messages-wrapper {
      flex-grow: 1; /* Takes up remaining space */
      overflow-y: auto; /* Allows scrolling of messages */
      background: var(--bg);
      padding: 16px;
      position: relative; /* Needed for potential absolute positioned elements inside */
    }
    .messages {
      max-width: 945px; margin: 0 auto; display: flex;
      flex-direction: column; gap: 4px; padding-bottom: 10px; /* Space at bottom */
    }
    .messages-wrapper::-webkit-scrollbar { width: 8px; }
    .messages-wrapper::-webkit-scrollbar-track { background: transparent; }
    .messages-wrapper::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 4px; }
    .messages-wrapper::-webkit-scrollbar-thumb:hover { background: var(--scrollbar-thumb-hover); }

    /* Message base */
    .message {
      opacity: 0; transform: translateY(10px); animation: fadeInUp .3s forwards ease-out;
      position: relative; max-width: 90%; margin-bottom: 12px;
      display: flex; flex-direction: column;
    }
    @keyframes fadeInUp { to { opacity: 1; transform: translateY(0); } }
    .message .timestamp { font-size: 10px; color: var(--text-muted); margin-top: 4px; padding: 0 5px; }

    /* User Message */
    .message.user { align-self: flex-end; align-items: flex-end; }
    .message.user .message-content { display: flex; flex-direction: column; align-items: flex-end; }
    .message.user .message-bubble {
        background: var(--bubble-user); color: var(--bubble-user-text);
        padding: 10px 14px; border-radius: 16px; border-bottom-right-radius: 4px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.15); word-wrap: break-word;
        width: fit-content; max-width: 100%; order: 2; margin-top: 4px;
    }
     .message.user .message-bubble:empty { display: none; margin-top: 0;}
    .message.user .timestamp { text-align: right; padding-right: 10px; }

    /* User Message - File Block */
    .message.user .file-block {
        background: var(--bubble-file-bg); color: var(--bubble-file-text);
        border-radius: 8px; padding: 8px 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        display: flex; align-items: center; gap: 10px;
        max-width: 100%; width: fit-content; order: 1;
    }
    .message.user .file-block .file-icon svg { display: block; }
    .message.user .file-block .file-icon svg path[fill="#F8CA27"] { fill: var(--accent); }
    .message.user .file-block .file-icon svg path[fill="#F8EDC7"] { fill: var(--bubble-file-text); }
    .message.user .file-block .file-details { overflow: hidden; }
    .message.user .file-block .file-name { font-size: 14px; font-weight: 500; white-space: nowrap; text-overflow: ellipsis; overflow: hidden; }
    .message.user .file-block .file-info { font-size: 12px; color: var(--bubble-file-info-text); white-space: nowrap; }

    /* Assistant message */
    .message.assistant { align-self: flex-start; align-items: flex-start;}
    .message.assistant .message-content {
        padding: 4px 0; color: var(--bubble-assistant-text);
        word-wrap: break-word; max-width: 100%; line-height: 1.5;
    }
    .message.assistant .timestamp { text-align: left; padding-left: 5px; }

    /* Assistant Code Formatting */
    .message.assistant pre { background-color: var(--body-bg); padding: 12px; border-radius: 6px; overflow-x: auto; margin: 10px 0; border: 1px solid var(--input-bg); font-size: 0.9em; }
    .message.assistant code { font-family: Consolas, Monaco, 'Andale Mono', 'Ubuntu Mono', monospace; }
    .message.assistant code:not(pre code) { background-color: var(--body-bg); padding: 2px 5px; border-radius: 4px; font-size: 0.9em; border: 1px solid var(--input-bg); }
    .message.assistant strong { font-weight: 600; color: var(--text); }
    .message.assistant em { font-style: italic; }
    .message.assistant ul, .message.assistant ol { margin: 10px 0 10px 25px; }
    .message.assistant li { margin-bottom: 5px; }

    /* Error message */
     .message.error { align-self: flex-start; align-items: flex-start; }
     .message.error .message-content {
        padding: 10px 14px; color: var(--bubble-error-text);
        background: var(--bubble-error-bg); border: 1px solid var(--bubble-error-border);
        border-radius: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        width: fit-content; max-width: 100%;
    }
     .message.error .message-content strong { color: inherit; font-weight: 600; }
     .message.error .timestamp { text-align: left; padding-left: 5px;}

    /* Typing indicator */
    .typing-indicator {
      margin-bottom: 12px; align-self: flex-start; opacity: 1; transform: none;
      animation: fadeInUp .3s forwards ease-out; display: flex; align-items: center; gap: 8px;
    }
    .typing { display: flex; gap: 5px; align-items: center; padding: 8px 0; }
    .typing-dot { width: 8px; height: 8px; background: var(--text-muted); border-radius: 50%; animation: blink 1.2s infinite ease-in-out; }
    .typing-dot:nth-child(2) { animation-delay: 0.15s; }
    .typing-dot:nth-child(3) { animation-delay: 0.3s; }
    @keyframes blink { 0%, 80%, 100% { opacity: .3; transform: scale(0.8); } 40% { opacity: 1; transform: scale(1); } }
    .typing-indicator .timestamp { margin-top: 0; padding-left: 0; }

    /* Input area */
    .input-area {
      background: var(--header-bg); z-index: 20;
      padding: 10px 0; /* Default padding */
      flex-shrink: 0; box-shadow: 0 -2px 5px rgba(0,0,0,0.1);
      border-top: 1px solid var(--input-border);
    }
    .input-container { max-width: 945px; margin: 0 auto; padding: 0 16px; }

    /* File Preview */
    .file-preview { display: none; padding: 5px 0 10px; margin-top: -5px; }
    .file-preview-content {
      display: flex; align-items: center; justify-content: space-between;
      background: var(--bubble-file-bg); border-radius: 8px; padding: 6px 10px;
    }
    .file-preview-details { display: flex; gap: 8px; align-items: center; min-width: 0; }
    .file-preview-icon { flex-shrink: 0; }
    .file-preview-icon svg { display: block; width: 32px; height: 32px;}
    .file-preview-icon svg path[fill="#F8CA27"] { fill: var(--accent); }
    .file-preview-icon svg path[fill="#F8EDC7"] { fill: var(--bubble-file-text); }
    .file-preview-text { overflow: hidden; }
    .file-preview-name { font-size: 13px; color: var(--bubble-file-text); white-space: nowrap; text-overflow: ellipsis; overflow: hidden; }
    .file-preview-info { font-size: 11px; color: var(--bubble-file-info-text); white-space: nowrap; }
    .file-remove-btn {
       cursor: pointer; display: flex; align-items: center; justify-content: center;
       padding: 4px; border-radius: 50%; transition: background 0.2s;
       flex-shrink: 0; border: none; background: none;
    }
    .file-remove-btn:hover { background: rgba(128, 128, 128, 0.2); }
    .file-remove-btn .icon svg { width: 14px; height: 14px; display: block;}
    .file-remove-btn .icon svg path { fill: var(--text-muted); }

    /* Input Inner */
    .input-inner { display: flex; align-items: flex-end; gap: 10px; } /* Default alignment */
    .input-inner form { display: flex; width: 100%; align-items: flex-end; gap: 10px; }
    #chatInput {
      flex: 1; padding: 10px 14px; border: 1px solid var(--input-border);
      border-radius: 8px; background: var(--body-bg); color: var(--text);
      font-size: 14px; transition: border-color .2s;
      min-height: 40px; max-height: 150px; resize: none; line-height: 1.4;
      overflow-y: auto;
      scrollbar-width: thin;
      scrollbar-color: var(--textarea-scrollbar-thumb) var(--textarea-scrollbar-track);
    }
    #chatInput::-webkit-scrollbar { width: 8px; }
    #chatInput::-webkit-scrollbar-track { background: var(--textarea-scrollbar-track); border-radius: 4px; }
    #chatInput::-webkit-scrollbar-thumb { background-color: var(--textarea-scrollbar-thumb); border-radius: 4px; border: 2px solid var(--textarea-scrollbar-track); }
    #chatInput::-webkit-scrollbar-thumb:hover { background-color: var(--scrollbar-thumb-hover); }
    #chatInput:focus { outline: none; border-color: var(--input-border-focus); }
    #chatInput::placeholder { color: var(--text-muted); opacity: 0.7; }

    /* File Upload Button */
    .file-upload-btn-label {
      width: 40px; height: 40px; border-radius: 50%; background: var(--input-bg);
      display: flex; align-items: center; justify-content: center; cursor: pointer;
      transition: background .2s ease; flex-shrink: 0; border: none; padding: 0; color: #BABABD;
    }
    .file-upload-btn-label:hover { background: #4b5563; }
    .file-upload-btn-label input[type="file"] { display: none; }
    .file-upload-btn-label .ds-icon svg { width: 20px; height: 20px; display: block; }

    /* Send Button */
    #sendBtn {
      width: 40px; height: 40px; background: var(--send-button-bg); border: none;
      border-radius: 50%; display: flex; align-items: center; justify-content: center;
      cursor: pointer; transition: background .2s ease, opacity 0.2s ease;
      flex-shrink: 0; padding: 0; color: var(--send-button-icon);
    }
    #sendBtn:disabled { background: var(--button-disabled-bg); opacity: .6; cursor: default; }
    #sendBtn:hover:not(:disabled) { background: var(--send-button-hover-bg); }
    #sendBtn .ds-icon svg { width: 16px; height: 16px; display: block; }

    /* Spinner */
    .spinner {
        border: 3px solid var(--spinner-border); border-top: 3px solid var(--spinner-top);
        border-radius: 50%; width: 18px; height: 18px; animation: spin 1s linear infinite;
    }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    #sendBtn.loading .send-icon { display: none; }

    /* Responsive Design */
    @media (max-width: 768px) {
      :root { --sidebar-width: 220px; }
       #sidebar { position: fixed; top: 0; bottom: 0; left: 0; box-shadow: 2px 0 8px rgba(0,0,0,0.3); height: 100vh; } /* Ensure full height on mobile */
       #sidebar.open { width: var(--sidebar-width); }
       #main { margin-left: 0 !important; width: 100%; }
       .sidebar-header { height: 50px; } /* Adjust mobile header height */

      .messages, .input-container { max-width: 100%; padding: 0 10px; }

       /* --- MODIFICATION 2: Input Area Padding for Safe Area --- */
       .input-area {
          /* Base padding for visual spacing */
          padding: 8px 0 14px 0; /* T:8, R:0, B:14, L:0 */
          /* Add safe area inset to bottom padding */
          padding-bottom: calc(14px + env(safe-area-inset-bottom));
       }

       /* --- MODIFICATION 3: Vertically center buttons with textarea --- */
       .input-inner {
           display: flex;
           align-items: center; /* Center items vertically */
           gap: 8px;
       }
       /* Ensure form inside also respects centering if needed */
       .input-inner form {
           align-items: center;
       }
       /* ------------------------------------------------------ */

       #chatInput { padding: 8px 12px; min-height: 38px; }
       .file-upload-btn-label, #sendBtn { width: 38px; height: 38px; }
       .file-upload-btn-label .ds-icon svg { width: 18px; height: 18px; }
       #sendBtn .ds-icon svg { width: 14px; height: 14px; }

       .message { max-width: 95%; }
       .header { padding: 0 10px; height: 50px; }
       .header button { padding: 6px 8px; font-size: 13px; }
       .sidebar-toggle-btn { padding: 6px; }
       .header-icon { font-size: 18px; width: 18px; height: 18px; }
    }
  </style>
</head>
<body>

  <!-- Sidebar -->
  <div id="sidebar">
      <div class="sidebar-header">
          <button id="sidebarCloseBtn" title="Close History">
             <svg class="sidebar-close-icon" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
               <path fill-rule="evenodd" clip-rule="evenodd" d="M18.7071 6.70711C19.0976 6.31658 19.0976 5.68342 18.7071 5.29289C18.3166 4.90237 17.6834 4.90237 17.2929 5.29289L12 10.5858L6.70711 5.29289C6.31658 4.90237 5.68342 4.90237 5.29289 5.29289C4.90237 5.68342 4.90237 6.31658 5.29289 6.70711L10.5858 12L5.29289 17.2929C4.90237 17.6834 4.90237 18.3166 5.29289 18.7071C5.68342 19.0976 6.31658 19.0976 6.70711 18.7071L12 13.4142L17.2929 18.7071C17.6834 19.0976 18.3166 19.0976 18.7071 18.7071C19.0976 18.3166 19.0976 17.6834 18.7071 17.2929L13.4142 12L18.7071 6.70711Z" fill="currentColor"/>
             </svg>
         </button>
      </div>
     <div class="sidebar-content">
        <div id="conversationsList"></div>
     </div>
  </div>

  <!-- Main Content -->
  <div id="main">
    <div class="header">
       <div class="left-controls">
         <button class="sidebar-toggle-btn" id="sidebarOpenBtn" title="Open History">
             <svg class="header-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/></svg>
         </button>
         <button id="newChatBtn" title="Start a new conversation">
             <svg class="header-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
             New Chat
         </button>
       </div>
    </div>

    <div class="messages-wrapper" id="messagesWrapper">
      <div class="messages" id="messagesContainer"></div>
    </div>

    <div class="input-area">
      <div class="input-container">

        <!-- File Preview Area -->
        <div class="file-preview" id="filePreview">
          <div class="file-preview-content">
            <div class="file-preview-details">
              <div class="file-preview-icon">
                <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M7 9C7 6.79086 8.79086 5 11 5L18.6383 5C19.1906 5 19.6383 5.44772 19.6383 6V6.92308C19.6383 9.13222 21.4292 10.9231 23.6383 10.9231H24C24.5523 10.9231 25 11.3708 25 11.9231V23C25 25.2091 23.2091 27 21 27H11C8.79086 27 7 25.2091 7 23V9Z" fill="#F8CA27"></path><g filter="url(#filter0_d_602_422_preview)"><path d="M19.6602 6.92458V5.84766L24.4126 10.9246H23.6602C21.451 10.9246 19.6602 9.13372 19.6602 6.92458Z" fill="#F8EDC7"></path></g><defs><filter id="filter0_d_602_422_preview" x="19.1602" y="5.34766" width="7.75195" height="8.07617" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB"><feFlood flood-opacity="0" result="BackgroundImageFix"></feFlood><feColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0" result="hardAlpha"></feColorMatrix><feOffset dx="1" dy="1"></feOffset><feGaussianBlur stdDeviation="0.75"></feGaussianBlur><feComposite in2="hardAlpha" operator="out"></feComposite><feColorMatrix type="matrix" values="0 0 0 0 0.591623 0 0 0 0 0.452482 0 0 0 0 0.0698445 0 0 0 0.25 0"></feColorMatrix><feBlend mode="normal" in2="BackgroundImageFix" result="effect1_dropShadow_602_422_preview"></feBlend><feBlend mode="normal" in="SourceGraphic" in2="effect1_dropShadow_602_422_preview" result="shape"></feBlend></filter></defs></svg>
              </div>
              <div class="file-preview-text">
                <div class="file-preview-name" id="fileNamePreview">example.json</div>
                <div class="file-preview-info" id="fileInfoPreview">JSON 0KB</div>
              </div>
            </div>
            <button class="file-remove-btn" id="removeFileBtn" title="Remove file">
                <div class="icon">
                  <svg viewBox="0 0 8 8" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M7.45.549a.777.777 0 0 1 0 1.098L1.648 7.451A.776.776 0 1 1 .55 6.353L6.353.55a.776.776 0 0 1 1.098 0z" fill="currentColor"/><path d="M.55.548a.776.776 0 0 1 1.097 0l5.804 5.805A.777.777 0 0 1 6.353 7.45L.549 1.646a.777.777 0 0 1 0-1.098z" fill="currentColor"/></svg>
                </div>
            </button>
          </div>
        </div>

        <!-- Input Form -->
        <div class="input-inner">
          <form id="chatForm">
            <!-- File Upload Button -->
            <label for="fileInput" class="file-upload-btn-label" title="Attach file">
              <input type="file" id="fileInput" accept=".png,.jpg,.jpeg,.webp,.heic,.heif,.txt,.pdf,.doc,.docx,.xls,.xlsx,.csv,.json, .py, .js, .html, .css, .java, .c, .cpp, .php, .rb, .swift, .kt, .go, .ts, .md"/>
               <div class="ds-icon">
                   <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 14 20" fill="none">
                       <path d="M7 20c-1.856-.002-3.635-.7-4.947-1.94C.74 16.819.003 15.137 0 13.383V4.828a4.536 4.536 0 0 1 .365-1.843 4.75 4.75 0 0 1 1.087-1.567A5.065 5.065 0 0 1 3.096.368a5.293 5.293 0 0 1 3.888 0c.616.244 1.174.6 1.643 1.05.469.45.839.982 1.088 1.567.25.586.373 1.212.364 1.843v8.555a2.837 2.837 0 0 1-.92 2.027A3.174 3.174 0 0 1 7 16.245c-.807 0-1.582-.3-2.158-.835a2.837 2.837 0 0 1-.92-2.027v-6.22a1.119 1.119 0 1 1 2.237 0v6.22a.777.777 0 0 0 .256.547.868.868 0 0 0 .585.224c.219 0 .429-.08.586-.224a.777.777 0 0 0 .256-.546V4.828A2.522 2.522 0 0 0 7.643 3.8a2.64 2.64 0 0 0-.604-.876 2.816 2.816 0 0 0-.915-.587 2.943 2.943 0 0 0-2.168 0 2.816 2.816 0 0 0-.916.587 2.64 2.64 0 0 0-.604.876 2.522 2.522 0 0 0-.198 1.028v8.555c0 1.194.501 2.339 1.394 3.183A4.906 4.906 0 0 0 7 17.885a4.906 4.906 0 0 0 3.367-1.319 4.382 4.382 0 0 0 1.395-3.183v-6.22a1.119 1.119 0 0 1 2.237 0v6.22c-.002 1.754-.74 3.436-2.052 4.677C10.635 19.3 8.856 19.998 7 20z" fill="currentColor"></path>
                   </svg>
               </div>
            </label>

            <!-- Text Input -->
            <textarea id="chatInput" placeholder="Type a message or drop a file..." rows="1"></textarea>

            <!-- Send Button -->
            <button type="submit" id="sendBtn" disabled>
                <div id="sendBtnContent">
                     <div class="send-icon">
                         <div class="ds-icon">
                            <svg width="14" height="16" viewBox="0 0 14 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path fill-rule="evenodd" clip-rule="evenodd" d="M7 16c-.595 0-1.077-.462-1.077-1.032V1.032C5.923.462 6.405 0 7 0s1.077.462 1.077 1.032v13.936C8.077 15.538 7.595 16 7 16z" fill="currentColor"></path>
                                <path fill-rule="evenodd" clip-rule="evenodd" d="M.315 7.44a1.002 1.002 0 0 1 0-1.46L6.238.302a1.11 1.11 0 0 1 1.523 0c.421.403.421 1.057 0 1.46L1.838 7.44a1.11 1.11 0 0 1-1.523 0z" fill="currentColor"></path>
                                <path fill-rule="evenodd" clip-rule="evenodd" d="M13.685 7.44a1.11 1.11 0 0 1-1.523 0L6.238 1.762a1.002 1.002 0 0 1 0-1.46 1.11 1.11 0 0 1 1.523 0l5.924 5.678c.42.403.42 1.056 0 1.46z" fill="currentColor"></path>
                            </svg>
                         </div>
                     </div>
                     <!-- Spinner will be inserted here -->
                </div>
            </button>
          </form>
        </div>
      </div>
    </div>
  </div> <!-- End #main -->

  <script>
    // --- Constants ---
    const BACKEND_URL = "https://bn9u12783t.onrender.com/chat"; // <<<--- Your backend URL
    const CONVERSATION_PREFIX = 'chatHistory_';
    const MAX_TITLE_LENGTH = 35;

    // --- DOM Elements ---
    const sidebar = document.getElementById('sidebar');
    const sidebarOpenBtn = document.getElementById('sidebarOpenBtn');
    const sidebarCloseBtn = document.getElementById('sidebarCloseBtn');
    const mainContent = document.getElementById('main');
    const conversationsList = document.getElementById('conversationsList');
    const newChatBtn = document.getElementById('newChatBtn');

    const messagesWrapper = document.getElementById('messagesWrapper');
    const messagesContainer = document.getElementById('messagesContainer');
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const sendBtnContent = document.getElementById('sendBtnContent');
    const fileInput = document.getElementById('fileInput');
    const fileUploadBtnLabel = document.querySelector('.file-upload-btn-label');
    const filePreview = document.getElementById('filePreview');
    const fileNamePreviewEl = document.getElementById('fileNamePreview');
    const fileInfoPreviewEl = document.getElementById('fileInfoPreview');
    const removeFileBtn = document.getElementById('removeFileBtn');

    // --- State Variables ---
    let selectedFile = null;
    let isSending = false;
    let currentConversationId = null;
    let currentHistory = []; // Holds { role: 'user'|'model', parts: [ {text: '...'}, {file_data: {...}} ] }

    // --- Helper Functions ---
    function formatBytes(bytes, decimals = 2) {
        if (!+bytes) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
    }

    function getTimestamp() {
       return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function scrollChatToBottom(behavior = 'smooth') {
        // Scroll the wrapper containing the messages
        setTimeout(() => {
             messagesWrapper.scrollTo({ top: messagesWrapper.scrollHeight, behavior: behavior });
        }, 50); // Delay helps ensure new message is rendered
    }


    function sanitizeHTML(str) {
        if (typeof str !== 'string') return '';
        const temp = document.createElement('div');
        temp.textContent = str;
        return temp.innerHTML;
    }

    function renderMarkdown(text) {
        if (!text) return '';
        let html = sanitizeHTML(text);
        // Code blocks (``` ```)
        html = html.replace(/```(\w*?\n)?([\s\S]*?)```/g, (match, lang, code) => {
            const cleanedCode = code.endsWith('\n') ? code.slice(0, -1) : code;
            return `<pre><code>${cleanedCode}</code></pre>`;
        });
        // Inline code (`)
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        // Bold (** or __)
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/__(.*?)__/g, '<strong>$1</strong>');
        // Italic (* or _) - Careful not to match bold
        html = html.replace(/(?<![*\\])\*(?![*\s])(.*?)(?<![*\s])\*(?![*\\])/g, '<em>$1</em>');
        html = html.replace(/(?<![_\\])_(?![_\s])(.*?)(?<![_\s])_(?![_\\])/g, '<em>$1</em>');
        // --- Handling Newlines and Lists ---
        const parts = html.split(/(<pre>[\s\S]*?<\/pre>|<code.*?>[\s\S]*?<\/code>)/);
        let processedHtml = '';
        for (let i = 0; i < parts.length; i++) {
            if (parts[i] && !parts[i].startsWith('<pre') && !parts[i].startsWith('<code')) {
                let segment = parts[i];
                segment = segment.replace(/^(?:<br>|\s)*([*+-])\s+(.*?)(?=<br>|\s*$)/gm, (match, marker, item) => `<li>${item.trim()}</li>`);
                segment = segment.replace(/(<li>.*?<\/li>)+/gs, '<ul>$&</ul>');
                segment = segment.replace(/<\/ul>\s*<ul>/g, '');
                segment = segment.replace(/<ul>\s*/g, '<ul>').replace(/\s*<\/ul>/g, '</ul>');
                // Convert newlines to <br> EXCEPT inside <ul>...</ul>
                let inList = false;
                segment = segment.split(/(\n)/).map(line => {
                   if (line.includes('<ul>')) inList = true;
                   if (line.includes('<\/ul>')) inList = false;
                   if (line === '\n' && !inList) return '<br>';
                   return line;
                }).join('');

                processedHtml += segment;
            } else if (parts[i]) {
                processedHtml += parts[i]; // Add code blocks back unmodified
            }
        }
        html = processedHtml.replace(/<ul><br>/g, '<ul>').replace(/<br><\/ul>/g, '</ul>'); // Cleanup inside lists
        html = html.replace(/<\/ul><br><ul>/g, ''); // Cleanup between lists
        html = html.replace(/<ul>\s*<\/ul>/g, ''); // Remove empty lists
        return html;
    }


    function setSendingState(sending) {
        isSending = sending;
        chatInput.disabled = sending;
        fileInput.disabled = sending;
        fileUploadBtnLabel.style.cursor = sending ? 'default' : 'pointer';
        fileUploadBtnLabel.style.opacity = sending ? 0.6 : 1;
        removeFileBtn.disabled = sending;

        const hasContent = chatInput.value.trim() !== '' || selectedFile !== null;
        sendBtn.disabled = sending || !hasContent;

        if (sending) {
            sendBtn.classList.add('loading');
            sendBtnContent.innerHTML = '<div class="spinner"></div>';
        } else {
            sendBtn.classList.remove('loading');
             sendBtnContent.innerHTML = `
                <div class="send-icon">
                    <div class="ds-icon">
                        <svg width="14" height="16" viewBox="0 0 14 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path fill-rule="evenodd" clip-rule="evenodd" d="M7 16c-.595 0-1.077-.462-1.077-1.032V1.032C5.923.462 6.405 0 7 0s1.077.462 1.077 1.032v13.936C8.077 15.538 7.595 16 7 16z" fill="currentColor"></path>
                            <path fill-rule="evenodd" clip-rule="evenodd" d="M.315 7.44a1.002 1.002 0 0 1 0-1.46L6.238.302a1.11 1.11 0 0 1 1.523 0c.421.403.421 1.057 0 1.46L1.838 7.44a1.11 1.11 0 0 1-1.523 0z" fill="currentColor"></path>
                            <path fill-rule="evenodd" clip-rule="evenodd" d="M13.685 7.44a1.11 1.11 0 0 1-1.523 0L6.238 1.762a1.002 1.002 0 0 1 0-1.46 1.11 1.11 0 0 1 1.523 0l5.924 5.678c.42.403.42 1.056 0 1.46z" fill="currentColor"></path>
                        </svg>
                     </div>
                </div>`;
        }
    }

    function createMessageElement(role, textContent, fileInfo = null, timestamp = null, animate = true) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', role); // role is 'user', 'assistant', or 'error' for display

        if(animate) {
            messageDiv.style.opacity = '0'; messageDiv.style.transform = 'translateY(10px)';
        } else {
             messageDiv.style.opacity = '1'; messageDiv.style.transform = 'translateY(0)';
        }

        const messageContentDiv = document.createElement('div');
        messageContentDiv.className = 'message-content';
        const displayTimestamp = timestamp || getTimestamp();

        let messageAdded = false; // Flag to check if we added any content

        if (role === 'user') {
            // Display file block first if present
            if (fileInfo && fileInfo.name) {
                const fileBlock = document.createElement('div');
                fileBlock.className = 'file-block';
                const sizeDisplay = (typeof fileInfo.size === 'number') ? formatBytes(fileInfo.size) : (fileInfo.size || ''); // Handle size being '?' from load
                const typeDisplay = (fileInfo.type && fileInfo.type !== 'unknown') ? fileInfo.type.split('/')[1]?.toUpperCase() : 'FILE';
                const fileInfoText = `${typeDisplay} ${sizeDisplay}`.trim();

                fileBlock.innerHTML = `
                    <div class="file-icon" style="font-size: 24px; width: 24px; height: 24px;">
                        <svg width="24" height="24" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M7 9C7 6.79086 8.79086 5 11 5L18.6383 5C19.1906 5 19.6383 5.44772 19.6383 6V6.92308C19.6383 9.13222 21.4292 10.9231 23.6383 10.9231H24C24.5523 10.9231 25 11.3708 25 11.9231V23C25 25.2091 23.2091 27 21 27H11C8.79086 27 7 25.2091 7 23V9Z" fill="#F8CA27"></path><g filter="url(#filter0_d_602_422_msg_user)"><path d="M19.6602 6.92458V5.84766L24.4126 10.9246H23.6602C21.451 10.9246 19.6602 9.13372 19.6602 6.92458Z" fill="#F8EDC7"></path></g><defs><filter id="filter0_d_602_422_msg_user" x="19.1602" y="5.34766" width="7.75195" height="8.07617" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB"><feFlood flood-opacity="0" result="BackgroundImageFix"></feFlood><feColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0" result="hardAlpha"></feColorMatrix><feOffset dx="1" dy="1"></feOffset><feGaussianBlur stdDeviation="0.75"></feGaussianBlur><feComposite in2="hardAlpha" operator="out"></feComposite><feColorMatrix type="matrix" values="0 0 0 0 0.591623 0 0 0 0 0.452482 0 0 0 0 0.0698445 0 0 0 0.25 0"></feColorMatrix><feBlend mode="normal" in2="BackgroundImageFix" result="effect1_dropShadow_602_422_msg_user"></feBlend><feBlend mode="normal" in="SourceGraphic" in2="effect1_dropShadow_602_422_msg_user" result="shape"></feBlend></filter></defs></svg>
                    </div>
                    <div class="file-details">
                        <div class="file-name" title="${sanitizeHTML(fileInfo.name)}">${sanitizeHTML(fileInfo.name)}</div>
                        <div class="file-info">${sanitizeHTML(fileInfoText)}</div>
                    </div>`;
                messageContentDiv.appendChild(fileBlock);
                messageAdded = true;
            }
            // Display text bubble if text exists
            if (textContent && textContent.trim()) {
                const bubble = document.createElement('div');
                bubble.className = 'message-bubble';
                bubble.innerHTML = sanitizeHTML(textContent); // User text is not markdown
                messageContentDiv.appendChild(bubble);
                messageAdded = true;
            }
        } else if (role === 'assistant') {
             if (textContent && textContent.trim()) {
                 messageContentDiv.innerHTML = renderMarkdown(textContent); // Render assistant response as markdown
                 messageAdded = true;
             }
        } else if (role === 'error') {
            if (textContent && textContent.trim()) {
                 const errorPrefix = "<strong>Error:</strong> ";
                 messageContentDiv.innerHTML = textContent.toLowerCase().startsWith('error:')
                     ? sanitizeHTML(textContent)
                     : errorPrefix + sanitizeHTML(textContent);
                 messageAdded = true;
             }
        }

        // Only append the message if some content was actually added
        if (!messageAdded) {
             console.warn("Skipping message element creation, no content found for role:", role, textContent, fileInfo);
             return null; // Indicate nothing was added
        }

        messageDiv.appendChild(messageContentDiv);

        const timestampDiv = document.createElement('div');
        timestampDiv.className = 'timestamp';
        timestampDiv.textContent = displayTimestamp;
        messageDiv.appendChild(timestampDiv);

        messagesContainer.appendChild(messageDiv);

        if (animate) {
            requestAnimationFrame(() => { // Ensure element is in DOM
                requestAnimationFrame(() => { // Trigger transition
                    messageDiv.style.opacity = '1'; messageDiv.style.transform = 'translateY(0)';
                });
            });
            scrollChatToBottom();
        }

        return { role, text: textContent || "", fileInfo, timestamp: displayTimestamp };
    }

    function showTypingIndicator() {
        if (messagesContainer.querySelector('.typing-indicator')) return;
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message assistant typing-indicator';
        typingDiv.innerHTML = `
            <div class="typing">
                <span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>
            </div>
            <div class="timestamp">${getTimestamp()}</div>`;
        messagesContainer.appendChild(typingDiv);
        scrollChatToBottom();
    }

    function removeTypingIndicator() {
        const typingDiv = messagesContainer.querySelector('.typing-indicator');
        if (typingDiv) typingDiv.remove();
    }

    // --- File Handling ---
    fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) { removeFile(); return; }
      selectedFile = file;
      fileNamePreviewEl.textContent = file.name;
      fileNamePreviewEl.title = file.name;
      fileInfoPreviewEl.textContent = `${file.type.split('/')[1]?.toUpperCase() || 'FILE'} ${formatBytes(file.size)}`;
      filePreview.style.display = 'block';
      updateSendButtonState();
      adjustTextareaHeight();
    });

    function removeFile() {
      fileInput.value = ''; selectedFile = null; filePreview.style.display = 'none';
      updateSendButtonState(); adjustTextareaHeight();
    }
    removeFileBtn.addEventListener('click', removeFile);

    // --- Input Handling ---
    chatInput.addEventListener('input', () => { updateSendButtonState(); adjustTextareaHeight(); });

    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); if (!sendBtn.disabled && !isSending) { sendMessage(); }
        }
    });

    function adjustTextareaHeight() {
        chatInput.style.height = 'auto';
        const maxHeight = 150; const scrollHeight = chatInput.scrollHeight;
        const newHeight = Math.min(scrollHeight, maxHeight);
        chatInput.style.height = newHeight + 'px';
        chatInput.style.overflowY = (scrollHeight > maxHeight) ? 'auto' : 'hidden';
    }

    function updateSendButtonState() {
         const hasContent = chatInput.value.trim() !== '' || selectedFile !== null;
         sendBtn.disabled = isSending || !hasContent;
    }

    // --- Chat History Functions ---
    function generateConversationId() { return `${CONVERSATION_PREFIX}${Date.now()}`; }

    function getConversationTitle(messagesForTitle) {
        if (!messagesForTitle || messagesForTitle.length === 0) return "New Chat";
        const firstUserMessage = messagesForTitle.find(m => m.role === 'user' && m.text?.trim());
        const firstFileMessage = messagesForTitle.find(m => m.fileInfo?.name);
        const firstAssistantMessage = messagesForTitle.find(m => m.role === 'assistant' && m.text?.trim());
        let titleSource = firstUserMessage?.text || firstFileMessage?.fileInfo?.name || firstAssistantMessage?.text || "Chat";
        let title = titleSource.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();
        return title.length > MAX_TITLE_LENGTH ? title.substring(0, MAX_TITLE_LENGTH) + '...' : title;
    }

    function saveCurrentConversation() {
         if (!currentHistory || currentHistory.length === 0) { console.log("Save skipped: currentHistory is empty."); return; }
         const historyToStore = currentHistory.map(histItem => {
             if (!histItem || !histItem.role || !histItem.parts || !Array.isArray(histItem.parts)) { console.warn("Save skipped item: Invalid structure.", histItem); return null; }
             return { role: histItem.role, parts: histItem.parts };
         }).filter(item => item !== null);
         if (historyToStore.length === 0) { console.log("Save skipped: No valid history items to store after filtering."); return; }
         const titleData = historyToStore.map(item => {
             const textPart = item.parts.find(p => p.text); const filePart = item.parts.find(p => p.file_data);
             let text = textPart ? textPart.text : ''; let fileInfo = null;
             if (filePart && filePart.file_data) { fileInfo = { name: filePart.file_data.file_uri?.split('/').pop() || 'file' }; }
             let displayRole = item.role === 'user' ? 'user' : 'assistant'; if (text.toLowerCase().startsWith('error:')) displayRole = 'error';
             return { role: displayRole, text: text, fileInfo: fileInfo };
         });
         const title = getConversationTitle(titleData); const date = Date.now();
         const currentId = currentConversationId || generateConversationId();
         try {
             const dataToStore = { id: currentId, title, date, history: historyToStore };
             const dataString = JSON.stringify(dataToStore);
             console.log(`Attempting to save to localStorage (key: ${currentId}):`, dataString.substring(0, 500) + '...');
             localStorage.setItem(currentId, dataString); currentConversationId = currentId;
             console.log(`Conversation ${currentId} saved successfully.`);
             loadConversationsList(); highlightCurrentConversation(currentId);
         } catch (e) { console.error("Error saving conversation to localStorage:", e); alert("Could not save conversation state."); }
     }

    function loadConversationsList() {
        conversationsList.innerHTML = ''; const keys = Object.keys(localStorage); const chatKeys = keys.filter(k => k.startsWith(CONVERSATION_PREFIX));
        const sortedChats = chatKeys.map(key => { try { const d = JSON.parse(localStorage.getItem(key)); return d ? { key: key, title: d.title || "Untitled", date: d.date || 0 } : null; } catch (e) { console.warn(`Failed to parse metadata for key ${key}:`, e); return null; } })
                                   .filter(i => i !== null).sort((a, b) => b.date - a.date);
        if (sortedChats.length === 0) { conversationsList.innerHTML = '<div style="padding: 15px; color: var(--text-muted); font-size: 13px; text-align: center;">No past conversations.</div>'; return; }
        sortedChats.forEach(chat => {
            const itemDiv = document.createElement('div'); itemDiv.className = 'conversation-item'; itemDiv.dataset.id = chat.key;
            const titleSpan = document.createElement('span'); titleSpan.className = 'conv-title'; titleSpan.textContent = chat.title; titleSpan.title = chat.title;
            const dateSpan = document.createElement('span'); dateSpan.className = 'conv-date'; dateSpan.textContent = new Date(chat.date).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });
            itemDiv.appendChild(titleSpan); itemDiv.appendChild(dateSpan);
            itemDiv.addEventListener('click', () => { if (!isSending) { loadConversation(chat.key); if (window.innerWidth <= 768) sidebar.classList.remove('open'); } });
            conversationsList.appendChild(itemDiv);
        });
         highlightCurrentConversation(currentConversationId);
    }

    function loadConversation(conversationId) {
        if (!conversationId || !localStorage.getItem(conversationId)) { console.warn(`Load failed: Conversation ID ${conversationId} not found.`); startNewConversation(); return; }
        console.log(`Loading conversation: ${conversationId}`);
        try {
            const storedDataString = localStorage.getItem(conversationId);
            console.log("Raw data loaded from localStorage:", storedDataString.substring(0, 500) + '...');
            const storedData = JSON.parse(storedDataString);
            if (storedData && storedData.history && Array.isArray(storedData.history)) {
                currentConversationId = conversationId; messagesContainer.innerHTML = ''; currentHistory = []; removeFile();
                storedData.history.forEach(savedItem => {
                    if (!savedItem || !savedItem.role || !savedItem.parts || !Array.isArray(savedItem.parts)) { console.warn("Load skipped item: Invalid structure in saved history.", savedItem); return; }
                    // 1. Add EXACT saved structure to currentHistory
                    currentHistory.push({ role: savedItem.role, parts: savedItem.parts });
                    // 2. Reconstruct display data for UI
                    let textForDisplay = ''; let fileInfoForDisplay = null; let displayRole = (savedItem.role === 'user') ? 'user' : 'assistant';
                    savedItem.parts.forEach(part => {
                        if (part.text) { textForDisplay += (textForDisplay ? " " : "") + part.text; }
                        else if (part.file_data && part.file_data.file_uri) { fileInfoForDisplay = { name: part.file_data.file_uri.split('/').pop() || 'Loaded File', type: part.file_data.mime_type || 'unknown', size: '?' }; }
                    });
                    if (savedItem.role === 'model' && textForDisplay.toLowerCase().startsWith('error:')) { displayRole = 'error'; }
                    createMessageElement(displayRole, textForDisplay, fileInfoForDisplay, savedItem.timestamp || getTimestamp(), false);
                });
                console.log("Final currentHistory after load:", JSON.stringify(currentHistory));
                highlightCurrentConversation(conversationId); scrollChatToBottom('instant');
                updateSendButtonState(); chatInput.value = ''; adjustTextareaHeight();
            } else { console.error(`Loaded data format invalid for ID: ${conversationId}.`); startNewConversation(); }
        } catch (e) { console.error(`Error loading or parsing conversation ${conversationId}:`, e); alert("Failed to load conversation."); startNewConversation(); }
    }

    function startNewConversation() {
        if (currentConversationId && currentHistory.length > 0) { console.log("Saving previous conversation before starting new one..."); saveCurrentConversation(); }
        currentConversationId = null; messagesContainer.innerHTML = ''; currentHistory = []; removeFile();
        chatInput.value = ''; adjustTextareaHeight(); updateSendButtonState(); highlightCurrentConversation(null);
        console.log("Started new conversation.");
    }

    function highlightCurrentConversation(conversationId) {
        document.querySelectorAll('.conversation-item').forEach(item => { item.classList.toggle('active', item.dataset.id === conversationId); });
    }

    // --- Send Message Logic ---
    async function sendMessage() {
        if (isSending) return;
        if (!BACKEND_URL || BACKEND_URL === "https://yourusername.pythonanywhere.com/chat") { alert("Please configure the BACKEND_URL constant in the script."); return; }
        const textInput = chatInput.value.trim(); const fileToProcess = selectedFile;
        if (!textInput && !fileToProcess) return;
        setSendingState(true);
        const userMessageToSend = { role: 'user', parts: [] };
        if (textInput) { userMessageToSend.parts.push({ text: textInput }); }
        let userFileInfoForDisplay = fileToProcess ? { name: fileToProcess.name, size: fileToProcess.size, type: fileToProcess.type } : null;
        createMessageElement('user', textInput, userFileInfoForDisplay, null, true);
        chatInput.value = ''; adjustTextareaHeight(); removeFile();
        showTypingIndicator();
        const formData = new FormData();
        if (textInput) formData.append('prompt', textInput);
        if (fileToProcess) formData.append('file', fileToProcess, fileToProcess.name);
        const historyToSend = currentHistory.filter(h => h && h.role && h.parts && h.parts.length > 0);
        formData.append('history', JSON.stringify(historyToSend));
        console.log("History BEING SENT to backend:", JSON.stringify(historyToSend).substring(0, 500) + '...');
        if (currentConversationId) { formData.append('conversation_id', currentConversationId); }
        let assistantMessageForHistory = null; let receivedFileDetails = null;
        try {
            console.log(`Sending request to backend: ${BACKEND_URL}`);
            const response = await fetch(BACKEND_URL, { method: 'POST', body: formData });
            removeTypingIndicator(); const data = await response.json();
            if (data && data.uploaded_file_details) {
                receivedFileDetails = data.uploaded_file_details; console.log("Received file details from backend:", receivedFileDetails);
                 if (receivedFileDetails.uri && receivedFileDetails.mime_type) {
                     userMessageToSend.parts.push({ file_data: { mime_type: receivedFileDetails.mime_type, file_uri: receivedFileDetails.uri } });
                     console.log("Added confirmed file_data part to userMessageToSend");
                 } else { console.warn("Received file details structure missing uri or mime_type:", receivedFileDetails); }
            }
            if (!response.ok || data.error) {
                let errorMsg = data.error || `Request failed with status ${response.status}`; console.error("Backend error:", errorMsg);
                createMessageElement('error', errorMsg); assistantMessageForHistory = { role: 'model', parts: [{ text: `Error: ${errorMsg}` }] };
            } else if (data.reply !== undefined && data.reply !== null) {
                createMessageElement('assistant', data.reply); assistantMessageForHistory = { role: 'model', parts: [{ text: data.reply }] };
            } else {
                 console.error("Invalid success response structure (missing reply):", data);
                 createMessageElement('error', "Received an empty or invalid response from the assistant."); assistantMessageForHistory = { role: 'model', parts: [{ text: "Error: Invalid response structure" }] };
            }
        } catch (error) {
            removeTypingIndicator(); console.error("Network/fetch error:", error);
            createMessageElement('error', `Network error: ${error.message}. Please check your connection.`); assistantMessageForHistory = { role: 'model', parts: [{ text: `Error: Network error - ${error.message}` }] };
        } finally {
            if (userMessageToSend.parts.length > 0) { currentHistory.push(userMessageToSend); console.log("Pushed User Turn to history:", JSON.stringify(userMessageToSend)); }
            else { console.warn("Skipping push of user turn to history as it had no parts."); }
            if (assistantMessageForHistory) { currentHistory.push(assistantMessageForHistory); console.log("Pushed Model Turn to history:", JSON.stringify(assistantMessageForHistory)); }
            setSendingState(false); saveCurrentConversation(); scrollChatToBottom();
        }
    }

    // --- Event Listeners & Initial Setup ---
    chatForm.addEventListener('submit', (e) => { e.preventDefault(); if (!isSending) sendMessage(); });
    sidebarOpenBtn.addEventListener('click', () => sidebar.classList.add('open'));
    sidebarCloseBtn.addEventListener('click', () => sidebar.classList.remove('open'));
    document.addEventListener('click', (e) => { if (window.innerWidth <= 768 && sidebar.classList.contains('open') && !sidebar.contains(e.target) && !sidebarOpenBtn.contains(e.target)) sidebar.classList.remove('open'); });
    newChatBtn.addEventListener('click', () => { if (!isSending) { startNewConversation(); if (window.innerWidth <= 768) sidebar.classList.remove('open'); } });

    // *** MODIFICATION 4: Add focus listener for keyboard handling (Existing comment in original code) ***
    chatInput.addEventListener('focus', () => {
        const isMobile = window.innerWidth <= 768;
        if (isMobile) {
            console.log("Mobile input focus detected, attempting scroll.");
            // Short delay allows keyboard animation to start
            setTimeout(() => {
                chatInput.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                console.log("scrollIntoView called for chatInput.");
            }, 200); // Adjust delay if necessary (100-300ms range)
        }
    });

    // *** NEW MODIFICATION: Handle pasting images into chatInput ***
    function handlePaste(event) {
        const items = event.clipboardData?.items;
        if (!items) return;

        let pastedImageFile = null;
        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image') !== -1) {
                pastedImageFile = items[i].getAsFile();
                break;
            }
        }

        if (pastedImageFile) {
            event.preventDefault(); // Prevent default paste behavior (e.g., pasting as base64 text or an <img> tag)

            // Ensure the file has a name. Browsers might provide a generic one or none.
            // Create a new File object with a generated name if needed.
            if (!pastedImageFile.name) {
                const extension = pastedImageFile.type.split('/')[1] || 'png'; // Default to png
                const fileName = `pasted_image_${Date.now()}.${extension}`;
                selectedFile = new File([pastedImageFile], fileName, { type: pastedImageFile.type });
            } else {
                selectedFile = pastedImageFile;
            }

            // Update UI with the pasted file
            fileNamePreviewEl.textContent = selectedFile.name;
            fileNamePreviewEl.title = selectedFile.name; // For tooltip on hover
            const fileTypeDisplay = selectedFile.type.split('/')[1]?.toUpperCase() || 'IMAGE';
            fileInfoPreviewEl.textContent = `${fileTypeDisplay} ${formatBytes(selectedFile.size)}`;
            filePreview.style.display = 'block';

            updateSendButtonState();
            adjustTextareaHeight();

            // Clear the actual file input element if a file was previously selected via the button.
            // This ensures the pasted image is the one to be sent.
            fileInput.value = '';
            console.log("Image pasted and processed:", selectedFile.name, selectedFile.size);
        }
        // If no image is found, the default paste behavior (for text, etc.) will proceed.
    }
    chatInput.addEventListener('paste', handlePaste);
    // *** END NEW MODIFICATION ***


    // Initial Page Load Setup
    updateSendButtonState(); adjustTextareaHeight(); loadConversationsList();
    try {
        const lastConvKey = Object.keys(localStorage).filter(k => k.startsWith(CONVERSATION_PREFIX)).map(k => { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } }).filter(d => d && d.date).sort((a,b) => b.date - a.date)[0]?.id;
        if(lastConvKey) { console.log("Loading last conversation:", lastConvKey); loadConversation(lastConvKey); }
        else { console.log("No previous conversation found, starting new."); startNewConversation(); }
    } catch (e) { console.error("Error trying to load last conversation:", e); startNewConversation(); }
    console.log("Chat interface initialized. Backend URL:", BACKEND_URL);
    if (!BACKEND_URL || BACKEND_URL === "https://yourusername.pythonanywhere.com/chat") { alert("Reminder: Update the BACKEND_URL constant in the script!"); createMessageElement('error', "Frontend not configured: BACKEND_URL needs to be set.", null, null, false); }
    window.addEventListener('beforeunload', (event) => { if (currentHistory && currentHistory.length > 0 && !isSending) { console.log("Saving conversation state before page unload..."); saveCurrentConversation(); } });

  </script>
</body>
</html>
