// Configuration for the candlestick chart
localStorage.debug = "*";
const chartProperties = {
    layout: {
        background: { color: "#222" },
        textColor: "#DDD",
    },
    grid: {
        vertLines: { color: "#444" },
        horzLines: { color: "#444" },
    },
    timeScale: {
        timeVisible: true,
        secondsVisible: false,
    },
};

// Check if the DOM element for the chart is available
const domElement = document.getElementById("tvchart");

if (domElement) {
    console.log("Chart DOM element found");
} else {
    console.error("Chart DOM element not found");
}

const chart = LightweightCharts.createChart(domElement, chartProperties);
const candleSeries = chart.addCandlestickSeries();
const clusterMarkerSeries = chart.addLineSeries({
    color: "transparent", // Hide the line
    lineWidth: 0,
    crosshairMarkerVisible: false,
    lastValueVisible: false,
    priceLineVisible: false,
});

let isListenersBound = false; // Flag to avoid multiple bindings
let dataPoints = [];
let lastInformation = null;
let maxDataPoints = 60 * 24 * 4;

// Initialize global marker arrays
let clusterMarkers = [];
let tradeMarkers = [];
let clusterAnnotationsVisible = false; // State of the toggle

function isNewDataPoint(lastDataPoint, newDataPoint) {
    return !lastDataPoint || lastDataPoint.time !== newDataPoint.time;
}

function fetchModelNames() {
    fetch("/get_model_names")
        .then((response) => response.json())
        .then((models) => {
            const dropdown = document.getElementById("model-select");
            if (dropdown) {
                models.forEach((model) => {
                    const option = document.createElement("option");
                    option.value = model;
                    option.textContent = model;
                    dropdown.appendChild(option);
                });

                const urlParams = new URLSearchParams(window.location.search);
                let selectedModel = urlParams.get("model");
                if (!selectedModel || !models.includes(selectedModel)) {
                    selectedModel = "RSI";
                }
                dropdown.value = selectedModel;
            } else {
                console.error("Model select dropdown not found");
            }
        })
        .catch((err) => console.error("Failed to fetch model names:", err));
}

function updateClusterAnnotations() {
    if (!clusterAnnotationsVisible) {
        clusterMarkerSeries.setData([]); // Clear data
        clusterMarkerSeries.setMarkers([]); // Clear markers
        return;
    }

    // Set data points at high prices
    const clusterData = dataPoints.map((dataPoint) => ({
        time: dataPoint.time,
        value: dataPoint.high, // Use the high price
    }));

    clusterMarkerSeries.setData(clusterData);

    // Set markers at those data points
    const clusterMarkers = dataPoints.map((dataPoint) => {
        if (dataPoint.cluster === null || dataPoint.cluster === undefined) {
            return null; // Skip if cluster is undefined
        }

        let color;
        if (dataPoint.cluster === 0) {
            color = "#00FFFF"; // Cyan
        } else if (dataPoint.cluster === 1) {
            color = "#A52A2A"; // Brown
        } else {
            return null; // Skip if cluster is invalid
        }

        return {
            time: dataPoint.time,
            position: "inBar", // Position is irrelevant here
            color: color,
            shape: "circle",
            size: 2, // Adjust size as needed
            text: "", // Optional text
        };
    }).filter((marker) => marker !== null); // Remove null markers

    clusterMarkerSeries.setMarkers(clusterMarkers);
}

function updateAllAnnotations() {
    const allMarkers = clusterMarkers.concat(tradeMarkers);
    candleSeries.setMarkers(allMarkers);
}

function fetchAndUpdateLatestData() {
    fetch("/get_latest")
        .then((res) => res.json())
        .then((responseData) => {
            if (responseData.data && responseData.data.length > 0) {
                const latestData = responseData.data[0];
                console.log("Received new kline:", latestData);

                const lastDataPoint = dataPoints.length > 0
                    ? dataPoints[dataPoints.length - 1]
                    : null;

                if (lastDataPoint && lastDataPoint.time === latestData.time) {
                    // Update the existing data point with new data (e.g., updated cluster assignment)
                    dataPoints[dataPoints.length - 1] = latestData;

                    // Update annotations
                    updateClusterAnnotations();
                    updateAnnotation();
                } else {
                    // New data point
                    candleSeries.update(latestData);
                    dataPoints.push(latestData);

                    if (dataPoints.length > maxDataPoints) {
                        dataPoints.shift();
                        candleSeries.setData(dataPoints);
                    }

                    // Update annotations
                    updateClusterAnnotations();
                    updateAnnotation();
                }
            }
        })
        .catch((err) => console.error("Failed to fetch data:", err));
}

// Fetch candlestick data and set it to the chart
function fetchCandles() {
    fetch("/get_range")
        .then((res) => res.json())
        .then((data) => {
            maxDataPoints = data.range;
        })
        .catch((err) => console.error(err));

    fetch("/fetch")
        .then((res) => res.json())
        .then((data) => {
            candleSeries.setData(data);
            dataPoints = [...data];
            updateClusterAnnotations(); // Update cluster annotations
            updateAnnotation(); // Update trade annotations
        })
        .catch((err) => console.error(err));
}

function getModelFromURL() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get("model");
}

function handleModelDropdown() {
    fetchModelNames();

    const dropdown = document.getElementById("model-select");
    if (dropdown) {
        dropdown.addEventListener("change", function () {
            const newModel = this.value;
            window.location.href = `/model_dash?model=${newModel}`;
        });
    } else {
        console.error("Model select dropdown not found");
    }
}

function postData(url = "", data = {}) {
    return fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
    })
        .then((response) => response.json())
        .then((data) => {
            if (
                data.status === "success" &&
                data.action === "updateNextUnitsChart"
            ) {
                const selectedModel = getModelFromURL();
                fetchModelParameters(selectedModel);
            }
        })
        .catch((error) => console.error("Error:", error));
}

function setupDynamicParams(dynamicParams, model) {
    const dynamicParamsContainer = document.getElementById("dynamic-params");
    dynamicParamsContainer.innerHTML = ""; // Clear previous content

    Object.entries(dynamicParams).forEach(([key, value], index) => {
        const paramItem = document.createElement("div");
        paramItem.classList.add("inline-group");

        const paramLabel = document.createElement("label");
        paramLabel.textContent = key;

        const paramInput = document.createElement("input");
        paramInput.type = "number";
        paramInput.value = value;
        paramInput.classList.add("input-small");
        paramInput.id = `dynamic-param-${index}`;

        const setButton = document.createElement("button");
        setButton.textContent = "Set";
        setButton.classList.add("btn-small");

        // Set dynamic parameter event listener
        setButton.addEventListener("click", () => {
            const updatedValue = paramInput.value;
            postData("/update_dynamic_param", {
                model: model,
                param: key,
                value: updatedValue,
            }).then(() => {
                console.log(`Updated ${key} to ${updatedValue}`);
            });
        });

        paramItem.appendChild(paramLabel);
        paramItem.appendChild(paramInput);
        paramItem.appendChild(setButton);
        dynamicParamsContainer.appendChild(paramItem);
    });
}

function setupFixedParams(params, model) {
    const statusDropdown = document.getElementById("model-status-toggle");
    statusDropdown.value = params.fixed["Model Status"].toLowerCase();

    if (!isListenersBound) {
        document.getElementById("submit-trade").addEventListener(
            "click",
            () => {
                const tradeType = document.getElementById("trade-type").value;
                const tradeUnitsInput = document.getElementById(
                    "trade-units-input",
                );
                const tradeUnits = tradeUnitsInput.value;

                if (!tradeUnits || tradeUnits <= 0) {
                    tradeUnitsInput.style.border = "2px solid red"; // Validation error
                } else {
                    tradeUnitsInput.style.border = "";
                    postData("/submit_trade", {
                        model,
                        trade_type: tradeType,
                        trade_units: tradeUnits,
                    });
                }
            },
        );

        document.getElementById("exit-position").addEventListener(
            "click",
            () => {
                postData("/exit_position", { model });
            },
        );

        document.getElementById("switch-trade").addEventListener(
            "click",
            () => {
                postData("/switch_trade", { model });
            },
        );

        statusDropdown.addEventListener("change", () => {
            const newStatus = statusDropdown.value; // Use the dropdown value directly
            postData("/update_model_status", {
                model: model,
                status: newStatus,
            });
        });

        isListenersBound = true; // Mark listeners as bound to avoid duplication
    }
}

function updateStatusColor(status) {
    const statusElement = document.getElementById("model-status");

    // Set color based on status
    switch (status.toLowerCase()) {
        case "neutral":
            statusElement.style.color = "yellow";
            statusElement.textContent = "Neutral";
            break;
        case "long":
            statusElement.style.color = "rgb(57, 163, 128)"; // Matching green color for returns
            statusElement.textContent = "Long";
            break;
        case "short":
            statusElement.style.color = "rgb(219, 87, 99)"; // Matching red color for returns
            statusElement.textContent = "Short";
            break;
        default:
            statusElement.style.color = "#DDD"; // Default color for unknown status
            statusElement.textContent = status; // Display the original status text
            break;
    }
}

// Modify the fetchModelParameters function to include a call to updateStatusColor
function fetchModelParameters(model) {
    fetch(`/get_model_params?model=${model}`)
        .then((res) => res.json())
        .then((params) => {
            const requiredElements = [
                document.getElementById("model-status"),
                document.getElementById("current-units"),
                document.getElementById("model-status-toggle"),
            ];

            if (requiredElements.some((el) => !el)) {
                console.error("Some DOM elements are missing.");
                return;
            }

            // Update the model status text and color
            const modelStatus = params.fixed.Status;
            document.getElementById("model-status").textContent = modelStatus;
            updateStatusColor(modelStatus); // Call the function to set color

            // Update other parameters
            document.getElementById("current-units").textContent =
                params.fixed["Current Units"];

            setupFixedParams(params, model);
            setupDynamicParams(params.dynamic, model);
        })
        .catch((err) => {
            console.error("Failed to fetch model parameters:", err);
        });
}

function fetchActiveTrade(model) {
    fetch(`/get_active_trade?model=${encodeURIComponent(model)}`)
        .then((response) => response.json())
        .then((data) => {
            if (data.active_trade) {
                updateProfitDisplay(
                    data.active_trade.profit,
                    data.active_trade.percentage,
                    data.active_trade.entry_price, // Pass the entry price
                );
            } else {
                updateProfitDisplay(null, null, null);
            }
        })
        .catch((error) => {
            console.error("Error fetching active trade:", error);
            updateProfitDisplay(null, null, null);
        });
}

let entryPriceLine = null;

function addEntryPriceLine(entryPrice) {
    // Remove existing entry price line if any
    removeEntryPriceLine();

    entryPriceLine = candleSeries.createPriceLine({
        price: entryPrice,
        color: "rgba(255, 165, 0, 0.8)", // Orange color
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true,
        title: "Entry Price",
    });
}

function removeEntryPriceLine() {
    if (entryPriceLine) {
        candleSeries.removePriceLine(entryPriceLine);
        entryPriceLine = null;
    }
}

function updateAnnotation() {
    const selectedModel = getModelFromURL();
    fetch(`/get_active_trade?model=${encodeURIComponent(selectedModel)}`)
        .then((res) => res.json())
        .then((data) => {
            if (data.active_trade) {
                const activeTrade = data.active_trade;
                const entryTime = parseInt(activeTrade.entry_time);
                const tradeType = activeTrade.trade_type;
                const entryPrice = parseFloat(activeTrade.entry_price);

                addAnnotation(entryTime, tradeType);
                addEntryPriceLine(entryPrice); // Add the entry price line
            } else {
                // No active trade
                removeAnnotation();
                removeEntryPriceLine();
            }
        })
        .catch((err) => console.error("Failed to fetch active trade:", err));
}

// Function to add trade annotation to the chart
function addAnnotation(entryTime, tradeType) {
    // Check if entryTime exists in dataPoints
    const dataTimes = dataPoints.map((dp) => dp.time);
    if (!dataTimes.includes(entryTime)) {
        // Find the closest time
        const closestTime = dataTimes.reduce((prev, curr) => {
            return (Math.abs(curr - entryTime) < Math.abs(prev - entryTime)
                ? curr
                : prev);
        });
        entryTime = closestTime;
    }

    const marker = {
        time: entryTime,
        position: tradeType === 1 ? "belowBar" : "aboveBar",
        color: tradeType === 1 ? "green" : "red",
        shape: tradeType === 1 ? "arrowUp" : "arrowDown",
        text: "Trade Entry",
    };

    tradeMarkers = [marker];

    updateAllAnnotations();
}

// Function to remove trade annotations from the chart
function removeAnnotation() {
    tradeMarkers = [];
    updateAllAnnotations();
}

// Function to update the profit/loss display
function updateProfitDisplay(profit, percentage, entryPrice) {
    const profitElement = document.getElementById("current-profit-loss");
    const percentageElement = document.getElementById(
        "current-percentage-return",
    );
    const entryPriceElement = document.getElementById("entry-price");

    if (profit !== null && percentage !== null && entryPrice !== null) {
        // Update profit display
        profitElement.textContent = profit.toFixed(2) + " USD";
        profitElement.style.color = profit >= 0
            ? "rgb(57, 163, 128)"
            : "rgb(219, 87, 99)";

        // Update percentage display
        percentageElement.textContent = percentage.toFixed(2) + "%";
        percentageElement.style.color = percentage >= 0
            ? "rgb(57, 163, 128)"
            : "rgb(219, 87, 99)";

        // Update entry price display
        entryPriceElement.textContent = entryPrice.toFixed(5) + " USD";
    } else {
        // No active trade
        profitElement.textContent = "No active trade";
        profitElement.style.color = "#DDD";

        percentageElement.textContent = "";
        percentageElement.style.color = "#DDD";

        entryPriceElement.textContent = "";
    }
}

function initializeEventListeners() {
    document.addEventListener("DOMContentLoaded", function () {
        const selectedModel = getModelFromURL();
        handleModelDropdown();
        fetchModelParameters(selectedModel); // Fetch parameters for the selected model
        fetchCandles();
        fetchAndUpdateLatestData();
        setInterval(fetchAndUpdateLatestData, 3000);
        setInterval(() => {
            fetchModelParameters(selectedModel);
            fetchActiveTrade(selectedModel); // Update active trade data
        }, 15000);

        // Add event listener for cluster toggle
        const clusterToggle = document.getElementById("cluster-toggle");
        if (clusterToggle) {
            clusterToggle.addEventListener("change", function () {
                clusterAnnotationsVisible = clusterToggle.checked;
                updateClusterAnnotations();
            });
        }
    });
}

initializeEventListeners();
