function fetchModelNames() {
    fetch('/get_model_names')
        .then((response) => response.json())
        .then((models) => {
            const dropdown = document.getElementById('model-dropdown');
            models.forEach((model) => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                dropdown.appendChild(option);
            });
        })
        .catch((error) => console.error('Error fetching models:', error));
}

// Attach event listener for dropdown after DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    const dropdown = document.getElementById('model-dropdown');
    if (dropdown) {
        dropdown.addEventListener('change', function() {
            const selectedModel = this.value;
            window.location.href = `/model_dash?model=${selectedModel}`;  
        });
    } else {
        console.error('Dropdown element not found!');
    }

    fetchModelNames();
});
