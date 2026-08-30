document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('query-form');
    const questionInput = document.getElementById('question');
    const limitInput = document.getElementById('limit');
    const loadingOverlay = document.getElementById('loading');
    const resultsLayout = document.getElementById('results');
    const imagesContainer = document.getElementById('images-container');
    const answerContainer = document.getElementById('answer-container');

    const API_URL = 'http://localhost:8000/query';

    form.addEventListener('submit', async (event) => {
        event.preventDefault();

        const question = questionInput.value.trim();
        const limit = parseInt(limitInput.value, 10);

        if (!question) return;

        // Show loading and hide previous results
        loadingOverlay.classList.remove('hidden');
        resultsLayout.classList.add('hidden');
        imagesContainer.innerHTML = '';
        answerContainer.innerHTML = '';

        try {
            const response = await fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ question, limit })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Server returned status ${response.status}`);
            }

            const data = await response.json();
            
            // 1. Render base64 context images on the left
            if (data.images && data.images.length > 0) {
                data.images.forEach((imgB64, index) => {
                    const card = document.createElement('div');
                    card.className = 'image-card';
                    
                    const header = document.createElement('div');
                    header.className = 'image-header';
                    header.innerHTML = `<span>Page Reference ${index + 1}</span>`;
                    
                    const img = document.createElement('img');
                    img.src = `data:image/jpeg;base64,${imgB64}`;
                    img.alt = `Reference Page ${index + 1}`;
                    
                    card.appendChild(header);
                    card.appendChild(img);
                    imagesContainer.appendChild(card);
                });
            } else {
                imagesContainer.innerHTML = '<p class="info-text">No reference pages were returned for this query.</p>';
            }

            // 2. Render markdown text answer on the right using Marked.js
            if (data.answer) {
                // marked.parse is provided globally by the marked script in index.html
                answerContainer.innerHTML = marked.parse(data.answer);
            } else {
                answerContainer.innerHTML = '<p class="info-text">No answer generated.</p>';
            }

            // Show results
            resultsLayout.classList.remove('hidden');

        } catch (error) {
            console.error('Error fetching query:', error);
            alert(`Query Failed: ${error.message}`);
        } finally {
            // Hide loading overlay
            loadingOverlay.classList.add('hidden');
        }
    });
});
