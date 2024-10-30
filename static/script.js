document.getElementById('send-button').addEventListener('click', sendMessage);
document.getElementById('clear-button').addEventListener('click', clearMessages);
document.getElementById('user-input').addEventListener('keydown', function (event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
});

// Drag-and-drop and file input handling
const dropArea = document.getElementById('dropArea');
const fileInput = document.getElementById('fileInput');
let parsedData = null;

// Drag-and-drop handling
dropArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropArea.classList.add('dragging');
});

dropArea.addEventListener('dragleave', () => {
    dropArea.classList.remove('dragging');
});

dropArea.addEventListener('drop', (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    handleFileUpload(file);
});

fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    handleFileUpload(file);
});

function handleFileUpload(file) {
    if (file.type !== 'text/csv') {
        alert('Please upload a valid CSV file.');
        return;
    }

    const reader = new FileReader();
    reader.onload = function (event) {
        const csvData = event.target.result;
        parsedData = d3.csvParse(csvData, d3.autoType);
        showDataPreview(parsedData);
    };
    reader.readAsText(file);
}

// Show preview of the CSV data
function showDataPreview(data) {
    const previewData = data;  // Show first 5 rows
    let tableHTML = "<table>";
    tableHTML += "<thead><tr>" + Object.keys(previewData[0]).map(key => `<th>${key}</th>`).join('') + "</tr></thead>";
    tableHTML += "<tbody>";
    previewData.forEach(row => {
        tableHTML += "<tr>" + Object.values(row).map(value => `<td>${value}</td>`).join('') + "</tr>";
    });
    tableHTML += "</tbody></table>";
    document.getElementById('dataPreview').innerHTML = tableHTML;
}

function removeMessage(element) {
    element.remove();
}

// Send message to backend and handle response
function sendMessage() {
    const userInput = document.getElementById('user-input').value.trim();
    if (userInput !== '') {
        addMessage('user', userInput);

        if (parsedData) {
            const loadingMessageId = addLoadingMessage("Working on it, this may take a few seconds...");

            // Send user input and dataset info to the backend
            fetch('http://127.0.0.1:8000/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: userInput,
                    columns: Object.keys(parsedData[0]),
                    dataTypes: getDataTypes(parsedData[0]),
                    FullData: parsedData.slice(0, 15),  // Send first 15 rows as sample data
                }),
            })
            .then(response => response.json())
            .then(data => {
                removeMessage(loadingMessageId);

                // Log the response from OpenAI to understand its "thinking process"
                console.log("OpenAI Response:", data);


                if (data.description) {
                    addMessage('bot', data.description);
                }
                
                // Check for the different types of responses
                if (data.vega_spec) {
                    addMessage('bot', "Here's the chart based on your request:", data.vega_spec);
                }
                
                if (data.analysis_result.startsWith("<table")) {
                    // If the response is HTML (like a table), render it using innerHTML
                    addMessage('bot', `Here is the analysis result: ${data.analysis_result}`, null, true);
                } else {
                    // If it's plain text, display it as text content
                    addMessage('bot', `Here is the analysis result:\n${data.analysis_result}`);
                }
                

                if (!data.vega_spec && !data.analysis_result && !data.description) {
                    addMessage('bot', 'Your question does not seem to be related to the uploaded dataset.');
                }
            })
            .catch((error) => {
                removeMessage(loadingMessageId);
                
                console.error('Error:', error);
                addMessage('bot', 'An error occurred while processing your request.');
            });
        } else {
            addMessage('bot', "Please upload a CSV file first.");
        }

        document.getElementById('user-input').value = '';  // Clear input field
    }
}

function clearMessages() {
    const chatHistory = document.getElementById('chat-history');
    while (chatHistory.firstChild) {
        chatHistory.removeChild(chatHistory.firstChild);
    }
    console.log('Chat history cleared');
    chatHistory.scrollTop = 0;
}

function getDataTypes(row) {
    const dataTypes = {};
    for (const key in row) {
        const value = row[key];
        if (typeof value === 'number') {
            dataTypes[key] = 'quantitative';
        } else if (value instanceof Date) {
            dataTypes[key] = 'temporal';
        } else {
            dataTypes[key] = 'nominal';
        }
    }
    return dataTypes;
}

function addLoadingMessage(text) {
    const chatHistory = document.getElementById('chat-history');
    const loadingMessageElement = document.createElement('div');
    const avatarElement = document.createElement('img');
    const messageContentElement = document.createElement('div');

    loadingMessageElement.classList.add('chat-message', 'bot-message');
    avatarElement.classList.add('avatar');
    avatarElement.src = 'https://img.rolandberger.com/content_assets/content_images/captions/Roland_Berger-24_2195_Humanoid_robots-IT_image_caption_none.jpg';
    avatarElement.alt = 'Bot Avatar';

    messageContentElement.classList.add('message-content');
    messageContentElement.innerHTML = `
        <p>${text}</p>
        <div class="spinner"></div>
    `;

    loadingMessageElement.appendChild(avatarElement);
    loadingMessageElement.appendChild(messageContentElement);
    chatHistory.appendChild(loadingMessageElement);
    chatHistory.scrollTop = chatHistory.scrollHeight;

    return loadingMessageElement;
}

function addMessage(sender, text, chartSpec = null, isHTML = false) {
    const chatHistory = document.getElementById('chat-history');
    const messageElement = document.createElement('div');
    const avatarElement = document.createElement('img');
    const messageContentElement = document.createElement('div');

    messageElement.classList.add('chat-message');
    avatarElement.classList.add('avatar');
    messageContentElement.classList.add('message-content');

    // Conditionally set HTML or text content based on the isHTML flag
    if (isHTML) {
        messageContentElement.innerHTML = text;  // Render as HTML
    } else {
        messageContentElement.textContent = text;  // Render as plain text
    }

    if (sender === 'user') {
        messageElement.classList.add('user-message');
        avatarElement.src = 'https://easydrawingguides.com/wp-content/uploads/2017/05/how-to-draw-a-boy-featured-image-1200-1-466x1024.png';
        avatarElement.alt = 'User Avatar';
    } else if (sender === 'bot') {
        messageElement.classList.add('bot-message');
        avatarElement.src = 'https://img.rolandberger.com/content_assets/content_images/captions/Roland_Berger-24_2195_Humanoid_robots-IT_image_caption_none.jpg';
        avatarElement.alt = 'Bot Avatar';
    }

    messageElement.appendChild(avatarElement);
    messageElement.appendChild(messageContentElement);

    if (chartSpec) {
        const chartContainer = document.createElement('div');
        chartContainer.style.width = '100%';
        chartContainer.style.height = '300px';
        chartContainer.style.marginTop = '10px';
        messageContentElement.appendChild(chartContainer);

        vegaEmbed(chartContainer, chartSpec)
            .catch((error) => {
                console.error('Error rendering chart:', error);
                messageContentElement.textContent += ' (Failed to render chart)';
            });
    }

    chatHistory.appendChild(messageElement);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}



