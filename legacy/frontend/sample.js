(function() {
  // Load Tailwind CSS
  document.head.insertAdjacentHTML('beforeend', '<link href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.16/tailwind.min.css" rel="stylesheet">');

  // Dynamically load jQuery and UUID libraries
  function loadScript(url, callback) {
    var script = document.createElement("script");
    script.type = "text/javascript";
    if (script.readyState) { // For IE <9
      script.onreadystatechange = function() {
        if (script.readyState == "loaded" || script.readyState == "complete") {
          script.onreadystatechange = null;
          callback();
        }
      };
    } else { // Other browsers
      script.onload = function() {
        callback();
      };
    }
    script.src = url;
    document.head.appendChild(script);
  }

  // Load jQuery
  loadScript("https://code.jquery.com/jquery-3.6.0.min.js", function() {
    // Load UUID after jQuery
    loadScript("https://cdn.jsdelivr.net/npm/uuid@8.3.2/dist/umd/uuid.min.js", function() {
      // Initialize the chat widget
      initChatWidget();
    });
  });

  function initChatWidget() {
    // Inject custom CSS styles
    const style = document.createElement('style');
    style.innerHTML = `
    .show {
        display: flex !important;
    }
    .bg-amber-300 {
      background-color: #DACB84;
    }
    #chat-widget-container {
      position: fixed;
      bottom: 20px;
      right: 20px;
      flex-direction: column;
      z-index: 9999;
    }
    #chat-popup {
      width: 350px;
      height: 500px;
      max-height: 70vh;
      display: none;
      background-color: white;
      border: 1px solid #ccc;
      border-radius: 10px;
      flex-direction: column;
      overflow: hidden;
      position: absolute;
      bottom: 80px;
      right: 0;
      transition: all 0.3s;
    }
    @media (max-width: 768px) {
      #chat-popup {
        position: fixed;
        top: 0;
        right: 0;
        bottom: 0;
        left: 0;
        width: 100%;
        height: 100%;
        max-height: 100%;
        border-radius: 0;
      }
    }
    #chat-header {
      background-color: #DACB84;
      color: white;
      padding: 10px;
      text-align: center;
      position: relative;
    }
    #close-popup {
      position: absolute;
      right: 10px;
      top: 10px;
      background: none;
      border: none;
      color: white;
      font-size: 20px;
      cursor: pointer;
    }
    #chat-messages {
      flex: 1;
      padding: 10px;
      overflow-y: auto;
    }
    #chat-input-container {
      padding: 10px;
      border-top: 1px solid #ccc;
    }
    #chat-input {
      width: 70%;
      border: 1px solid #ccc;
      border-radius: 5px;
      padding: 10px;
      outline: none;
    }
    #chat-submit {
      background-color: #333;
      color: white;
      border: none;
      border-radius: 5px;
      padding: 10px 20px;
      cursor: pointer;
      margin-left: 10px;
    }
    .message {
      display: flex;
      margin-bottom: 10px;
    }
    .message.user .message-content {
      background-color: #333;
      color: white;
      align-self: flex-end;
    }
    .message.assistant .message-content {
      background-color: #f1f0f0;
      color: black;
      align-self: flex-start;
    }
    .message-content {
      max-width: 70%;
      word-wrap: break-word;
      padding: 10px;
      border-radius: 10px;
    }
    `;
    document.head.appendChild(style);

    // Ensure the body is ready
    if (document.body) {
      createChatContainer();
    } else {
      document.addEventListener('DOMContentLoaded', function() {
        createChatContainer();
      });
    }

    function createChatContainer() {
      // Create chat widget container
      const chatWidgetContainer = document.createElement('div');
      chatWidgetContainer.id = 'chat-widget-container';
      document.body.appendChild(chatWidgetContainer);

      // Inject the HTML structure
      chatWidgetContainer.innerHTML = `
        <div id="chat-bubble" class="w-16 h-16 bg-white rounded-full flex items-center justify-center cursor-pointer text-3xl">
          <img src="https://uc-ai.azurewebsites.net/assets/uc-ai-logo-6abfbb65.png" class="_chatIcon_3ejjm_64" aria-hidden="true">
        </div>
        <div id="chat-popup">
          <div id="chat-header" class="flex justify-between items-center p-4 bg-amber-300 text-white rounded-t-md">
            <h3 class="m-0 text-lg text-white">ARI</h3>
            <button id="close-popup" class="bg-transparent border-none text-white cursor-pointer">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
            </button>
          </div>
          <div id="chat-messages" class="flex-1 p-4 overflow-y-auto"></div>
          <div id="chat-input-container" class="p-4 border-t border-gray-200">
            <div class="flex space-x-4 items-center">
              <input type="text" id="chat-input" class="flex-1 border border-gray-300 rounded-md px-4 py-2 outline-none w-3/4" placeholder="Type your message...">
              <button id="chat-submit" class="bg-gray-800 text-white rounded-md px-4 py-2 cursor-pointer">Send</button>
            </div>
            <div class="flex text-center text-xs pt-4">
              <span class="flex-1">Powered by REI Labs</span>
            </div>
          </div>
        </div>
      `;

      // Add event listeners
      const chatInput = document.getElementById('chat-input');
      const chatSubmit = document.getElementById('chat-submit');
      const chatMessages = document.getElementById('chat-messages');
      const chatBubble = document.getElementById('chat-bubble');
      const chatPopup = document.getElementById('chat-popup');
      const closePopup = document.getElementById('close-popup');

      let messageHistory = [];

      chatSubmit.addEventListener('click', function() {
        const message = chatInput.value.trim();
        if (!message) return;
        chatInput.value = '';
        addMessage('user', message);
        onUserRequest(message);
      });

      chatInput.addEventListener('keyup', function(event) {
        if (event.key === 'Enter') {
          chatSubmit.click();
        }
      });

      chatBubble.addEventListener('click', function() {
        togglePopup();
      });

      closePopup.addEventListener('click', function() {
        togglePopup();
      });

      function togglePopup() {
        const chatPopup = document.getElementById('chat-popup');
        chatPopup.classList.toggle('show');
        if (chatPopup.classList.contains('show')) {
            document.getElementById('chat-input').focus();
        }
      }

      function addMessage(role, content) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${role}`;
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.innerHTML = content;
        messageElement.appendChild(messageContent);
        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }

      function onUserRequest(message) {
        const userMessage = {
          id: uuid.v4(),
          role: "user",
          content: message,
          date: new Date().toISOString()
        };

        messageHistory.push(userMessage);

        // Replace 'YOUR_BACKEND_ENDPOINT' with your actual backend endpoint
        const url = 'https://uc-ai.azurewebsites.net/conversation';

        fetchResponse(url, { messages: messageHistory });
      }

      function fetchResponse(url, body) {
        let assistantMessage = '';
        let buffer = '';
      
        console.log('Sending request to:', url);
        console.log('Request body:', body);
      
        $.ajax({
          type: "POST",
          url: url,
          data: JSON.stringify(body),
          contentType: "application/json",
          xhrFields: {
            onprogress: function (e) {
              const response = e.currentTarget.response;
              buffer += response.substring(buffer.length); // Keep track of unread response
      
              // Split the response into chunks, where each chunk is separated by \n\n
              let chunks = buffer.split('\n\n');
              buffer = chunks.pop(); // Keep the last incomplete chunk in the buffer
      
              chunks.forEach(chunk => {
                if (chunk.trim() !== '') {
                  try {
                    // Parse the chunk as JSON
                    const data = JSON.parse(chunk);
      
                    // Handle assistant's messages
                    if (data.choices && data.choices[0]?.delta?.content) {
                      const content = data.choices[0].delta.content;
                      assistantMessage += content;
                      addAssistantTyping(content);
                    }
      
                  } catch (err) {
                    console.error('Error parsing chunk:', err);
                    console.error('Problematic chunk:', chunk);
                  }
                }
              });
            }
          },
          success: function (result) {
            console.log('Request completed successfully');
          },
          error: function (xhr, status, error) {
            console.error('Ajax error:', status, error);
            console.error('Response text:', xhr.responseText);
            addMessage('assistant', 'Sorry, an error occurred.');
          }
        });
      }
      
      function addAssistantTyping(content) {
        console.log('Adding assistant typing:', content);
        const existingMessage = document.querySelector('.message.assistant:last-child .message-content');
        if (existingMessage) {
          existingMessage.innerHTML += content; // Append content to the last assistant message
        } else {
          addMessage('assistant', content); // Add new message if none exists
        }
        scrollChatToBottom();
      }
      
      function addMessage(role, content) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${role}`;
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.innerHTML = content;
        messageElement.appendChild(messageContent);
        document.querySelector('#chatMessages').appendChild(messageElement); // Assuming chatMessages is your div container
        scrollChatToBottom();
      }
      
      function scrollChatToBottom() {
        const chatMessages = document.querySelector('#chatMessages'); // Assuming chatMessages is your div container
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }      

    }
  }
})();