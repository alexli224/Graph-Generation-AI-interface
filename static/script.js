document.getElementById('send-button').addEventListener('click', sendMessage);
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

// Send message to backend and handle response
function sendMessage() {
    const userInput = document.getElementById('user-input').value.trim();
    if (userInput !== '') {
        addMessage('user', userInput);

        if (parsedData) {
            // Send user input and dataset info to the backend
            fetch('https://graph-generation-ai-interface.onrender.com/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: userInput,
                    columns: Object.keys(parsedData[0]),
                    dataTypes: getDataTypes(parsedData[0]),
                    FullData: parsedData.slice(0, 15),  // Send first 5 rows as sample data
                }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.vega_spec && data.description) {
                    addMessage('bot', data.description, data.vega_spec);  // Pass Vega spec to addMessage
                } else {
                    addMessage('bot', 'Failed to generate the chart.');
                }
            })
            .catch((error) => {
                console.error('Error:', error);
                addMessage('bot', 'An error occurred while generating the chart.');
            });
        } else {
            addMessage('bot', "Please upload a CSV file first.");
        }

        document.getElementById('user-input').value = '';  // Clear input field
    }
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

function addMessage(sender, text, chartSpec = null) {
    const chatHistory = document.getElementById('chat-history');
    const messageElement = document.createElement('div');
    const avatarElement = document.createElement('img');
    const messageContentElement = document.createElement('div');

    messageElement.classList.add('chat-message');
    avatarElement.classList.add('avatar');
    messageContentElement.classList.add('message-content');

    messageContentElement.textContent = text;

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

    // If chartSpec is provided, append the chart to the message
    if (chartSpec) {
        const chartContainer = document.createElement('div');
        chartContainer.style.width = '100%';
        chartContainer.style.height = '300px';
        chartContainer.style.marginTop = '10px'; // Space between the text and the chart
        messageContentElement.appendChild(chartContainer);

        // Use Vega-Lite to render the chart inside the message content
        vegaEmbed(chartContainer, chartSpec)
            .catch((error) => {
                console.error('Error rendering chart:', error);
                messageContentElement.textContent += ' (Failed to render chart)';
            });
    }

    chatHistory.appendChild(messageElement);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}



function renderChart(spec) {
    vegaEmbed('#chart', spec)
        .then(() => {
            document.getElementById('chart').style.display = 'block';  // Show the chart
        })
        .catch((error) => {
            console.error('Error rendering chart:', error);
            addMessage('bot', 'Failed to render the chart.');
        });
}


