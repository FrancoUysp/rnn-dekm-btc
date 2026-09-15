// Keep track of whether the table is expanded or collapsed
let tableExpanded = false;

function getModelFromURL() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get("model") || "all_models";
}

// Fetch returns for the selected model
function fetchModelReturns(model) {
    fetch(`/get_returns?model=${encodeURIComponent(model)}`)
        .then((response) => response.json())
        .then((data) => {
            const returnsDisplay = document.getElementById("returns-display");

            // Check if there's an error in data fetching
            if (data.error) {
                returnsDisplay.innerHTML = `<p>${data.error}</p>`;
                return;
            }

            // Sort positions by exit time in reverse chronological order
            const sortedPositions = sortPositionsByTime(data.positions);

            // Format and display the returns data
            returnsDisplay.innerHTML = `
                <h3>Returns for ${
                model === "all_models" ? "All Models" : model
            }:</h3>
                <div class="returns-summary">
                    <div class="return-item">
                        <h4>All Time Return:</h4>
                        <p>
                            <span class="label">Raw:</span>
                            <span class="value" style="color: ${
                data.all_time_return >= 0
                    ? "rgb(57, 163, 128)"
                    : "rgb(219, 87, 99)"
            };">${data.all_time_return.toFixed(3)} USD</span><br>
                            <span class="label">Percentage:</span>
                            <span class="value percentage" style="color: ${
                data.all_time_percentage >= 0
                    ? "rgb(57, 163, 128)"
                    : "rgb(219, 87, 99)"
            };">${(data.all_time_percentage * 100).toFixed(3)}%</span>
                        </p>
                    </div>
                    <div class="return-item">
                        <h4>Monthly Return:</h4>
                        <p>
                            <span class="label">Raw:</span>
                            <span class="value" style="color: ${
                data.monthly_return >= 0
                    ? "rgb(57, 163, 128)"
                    : "rgb(219, 87, 99)"
            };">${data.monthly_return.toFixed(3)} USD</span><br>
                            <span class="label">Percentage:</span>
                            <span class="value percentage" style="color: ${
                data.monthly_percentage >= 0
                    ? "rgb(57, 163, 128)"
                    : "rgb(219, 87, 99)"
            };">${(data.monthly_percentage * 100).toFixed(3)}%</span>
                        </p>
                    </div>
                    <div class="return-item">
                        <h4>Weekly Return:</h4>
                        <p>
                            <span class="label">Raw:</span>
                            <span class="value" style="color: ${
                data.weekly_return >= 0
                    ? "rgb(57, 163, 128)"
                    : "rgb(219, 87, 99)"
            };">${data.weekly_return.toFixed(3)} USD</span><br>
                            <span class="label">Percentage:</span>
                            <span class="value percentage" style="color: ${
                data.weekly_percentage >= 0
                    ? "rgb(57, 163, 128)"
                    : "rgb(219, 87, 99)"
            };">${(data.weekly_percentage * 100).toFixed(3)}%</span>
                        </p>
                    </div>
                    <div class="return-item">
                        <h4>Daily Return:</h4>
                        <p>
                            <span class="label">Raw:</span>
                            <span class="value" style="color: ${
                data.daily_return >= 0
                    ? "rgb(57, 163, 128)"
                    : "rgb(219, 87, 99)"
            };">${data.daily_return.toFixed(3)} USD</span><br>
                            <span class="label">Percentage:</span>
                            <span class="value percentage" style="color: ${
                data.daily_percentage >= 0
                    ? "rgb(57, 163, 128)"
                    : "rgb(219, 87, 99)"
            };">${(data.daily_percentage * 100).toFixed(3)}%</span>
                        </p>
                    </div>
                </div>
            `;

            // Create the returns plot
            createReturnsPlot(data.positions);

            // Create the pie chart
            createPieChart(data.positions);

            // Now update the trade history in reverse order
            updateTradeHistory(sortedPositions);
        })
        .catch((err) => {
            console.error("Failed to fetch returns:", err);
            document.getElementById("returns-display").innerHTML =
                `<p>Error fetching returns.</p>`;
        });
}

// Helper function to sort positions by exit time in reverse order
function sortPositionsByTime(positions) {
    return positions.sort((a, b) =>
        new Date(b.exit_time) - new Date(a.exit_time)
    );
}

function updateTradeHistory(positions) {
    const tableBody = document.querySelector("#trade-history tbody");

    // Clear the existing rows
    tableBody.innerHTML = "";

    // If no positions are available, show a placeholder row
    if (!positions || positions.length === 0) {
        tableBody.innerHTML =
            `<tr><td colspan="9">No trade history available.</td></tr>`;
        return;
    }

    // Helper function to check if a value is a valid number
    const isValidNumber = (value) => typeof value === "number" && !isNaN(value);

    // Create a fragment to append rows
    const fragment = document.createDocumentFragment();

    positions.forEach((position, index) => {
        // Parse numeric values
        const volume = parseFloat(position.volume);
        const entryPrice = parseFloat(position.entry_price);
        const exitPrice = parseFloat(position.exit_price);
        const profit = parseFloat(position.profit);
        const percentageReturn = parseFloat(position.percentage_return);

        const positionType = position.type === 0
            ? "Long"
            : position.type === 1
            ? "Short"
            : "N/A";

        const row = document.createElement("tr");

        // Assign 'hidden-row' class to rows beyond the first 5 if table is collapsed
        if (!tableExpanded && index >= 5) {
            row.classList.add("hidden-row");
        }

        row.innerHTML = `
            <td>${position.position_id || "N/A"}</td>
            <td>${positionType}</td>
            <td>${position.entry_time || "N/A"}</td>
            <td>${position.exit_time || "N/A"}</td>
            <td>${isValidNumber(volume) ? volume.toFixed(4) : "N/A"}</td>
            <td>${
            isValidNumber(entryPrice) ? entryPrice.toFixed(5) : "N/A"
        }</td>
            <td>${isValidNumber(exitPrice) ? exitPrice.toFixed(5) : "N/A"}</td>
            <td style="color: ${
            isValidNumber(profit) && profit >= 0
                ? "rgb(57, 163, 128)"
                : "rgb(219, 87, 99)"
        };">
                ${isValidNumber(profit) ? profit.toFixed(4) : "N/A"}
            </td>
            <td style="color: ${
            isValidNumber(percentageReturn) && percentageReturn >= 0
                ? "rgb(57, 163, 128)"
                : "rgb(219, 87, 99)"
        };">
                ${
            isValidNumber(percentageReturn)
                ? (percentageReturn * 100).toFixed(4)
                : "N/A"
        }%
            </td>
        `;

        fragment.appendChild(row);
    });

    tableBody.appendChild(fragment);

    // After updating the table, check if we need to show the toggle button
    const toggleButton = document.getElementById("toggle-table-rows");

    // If positions.length > 5, show the button
    if (positions.length > 5) {
        toggleButton.style.display = "block";
        // Set the button text based on the current state
        toggleButton.textContent = tableExpanded ? "Show Less" : "Show More";
    } else {
        // Hide the button if there are 5 or fewer positions
        toggleButton.style.display = "none";
    }
}

// Function to create the returns plot
function createReturnsPlot(positions) {
    if (!positions || positions.length === 0) {
        // No positions to plot
        document.getElementById("returns-plot").innerHTML =
            "<p>No returns data to plot.</p>";
        return;
    }

    // Prepare the data for cumulative percentage return over time
    let cumulativeReturns = [];
    let dates = [];
    let cumulativeReturn = 0;

    // Positions should be sorted in chronological order
    positions.sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time));

    positions.forEach((position) => {
        const percentageReturn = parseFloat(position.percentage_return) || 0;
        cumulativeReturn += percentageReturn; // No multiplication needed
        cumulativeReturns.push(cumulativeReturn);
        dates.push(position.exit_time);
    });

    const trace = {
        x: dates,
        y: cumulativeReturns,
        mode: "lines+markers",
        type: "scatter",
        name: "Cumulative Return (%)",
        line: { color: "rgb(57, 163, 128)" },
    };

    const data = [trace];

    const layout = {
        title: "Cumulative Percentage Returns Over Time",
        xaxis: {
            title: "Date",
            type: "date",
        },
        yaxis: {
            title: "Cumulative Return (%)",
        },
        plot_bgcolor: "#333",
        paper_bgcolor: "#333",
        font: {
            color: "#ddd",
        },
        margin: {
            l: 60,
            r: 20,
            t: 50,
            b: 50,
        },
    };

    Plotly.newPlot("returns-plot", data, layout, { responsive: true });
}

// Function to create the pie chart
function createPieChart(positions) {
    if (!positions || positions.length === 0) {
        // No positions to plot
        document.getElementById("pie-chart").innerHTML =
            "<p>No trade data to display.</p>";
        return;
    }

    let positiveTrades = 0;
    let negativeTrades = 0;

    positions.forEach((position) => {
        const profit = parseFloat(position.profit) || 0;
        if (profit >= 0) {
            positiveTrades += 1;
        } else {
            negativeTrades += 1;
        }
    });

    const data = [{
        values: [positiveTrades, negativeTrades],
        labels: ["Positive Trades", "Negative Trades"],
        type: "pie",
        marker: {
            colors: ["rgb(57, 163, 128)", "rgb(219, 87, 99)"],
        },
        textinfo: "label+percent",
        hoverinfo: "label+value+percent",
    }];

    const layout = {
        title: "Proportion of Positive and Negative Trades",
        plot_bgcolor: "#333",
        paper_bgcolor: "#333",
        font: {
            color: "#ddd",
        },
        margin: {
            l: 20,
            r: 20,
            t: 50,
            b: 20,
        },
    };

    Plotly.newPlot("pie-chart", data, layout, { responsive: true });
}

// Fetch model names for the dropdown
function fetchModelNames() {
    fetch("/get_model_names")
        .then((response) => response.json())
        .then((models) => {
            const dropdown = document.getElementById("model-select");

            // Clear existing options except the first one ("All Models")
            while (dropdown.options.length > 1) {
                dropdown.remove(1);
            }

            // Populate models
            models.forEach((model) => {
                const option = document.createElement("option");
                option.value = model;
                option.textContent = model;
                dropdown.appendChild(option);
            });

            // Preselect model from URL
            const selectedModel = getModelFromURL();
            dropdown.value = selectedModel;

            // Fetch returns for the selected model
            fetchModelReturns(selectedModel);
        })
        .catch((err) => console.error("Failed to fetch model names:", err));
}

// Event listener for model selection change
document.getElementById("model-select").addEventListener("change", function () {
    const selectedModel = this.value;
    fetchModelReturns(selectedModel);

    const newUrl = window.location.protocol + "//" + window.location.host +
        window.location.pathname + "?model=" +
        encodeURIComponent(selectedModel);
    window.history.replaceState({ path: newUrl }, "", newUrl);
});

document.getElementById("back-to-model-dash").addEventListener("click", () => {
    let selectedModel = document.getElementById("model-select").value ||
        "RSI";
    if (selectedModel === "all_models" || !selectedModel) {
        selectedModel = "RSI";
    }
    window.location.href = `/model_dash?model=${
        encodeURIComponent(selectedModel)
    }`;
});

// Event listener for the Show More / Show Less button
document.getElementById("toggle-table-rows").addEventListener(
    "click",
    function () {
        const hiddenRows = document.querySelectorAll(
            "#trade-history tbody .hidden-row",
        );
        if (tableExpanded) {
            // Collapse the table
            hiddenRows.forEach((row) => {
                row.style.display = "none";
            });
            this.textContent = "Show More";
            tableExpanded = false;
        } else {
            // Expand the table
            hiddenRows.forEach((row) => {
                row.style.display = "table-row"; // Use "table-row" here
            });
            this.textContent = "Show Less";
            tableExpanded = true;
        }
    },
);

// Initialize model names and set default state
document.addEventListener("DOMContentLoaded", function () {
    fetchModelNames();
    fetchModelReturns("all_models");
});
