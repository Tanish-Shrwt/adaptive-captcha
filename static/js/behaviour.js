let mouseMoves = 0;
let clicks = 0;
let typingStart = 0;
let typingTime = 0;
let pageStart = Date.now();

let mouseDisplay = document.getElementById("mouseActivity");
let timeDisplay = document.getElementById("responseTime");

// 🔥 Detect if values already exist (from Flask)
let initialMouse = mouseDisplay ? parseInt(mouseDisplay.innerText) : 0;
let initialTime = timeDisplay ? parseInt(timeDisplay.innerText) : 0;

// If page reloaded → start from previous values
if (!isNaN(initialMouse)) mouseMoves = initialMouse;
if (!isNaN(initialTime)) pageStart = Date.now() - initialTime;

// Mouse tracking
document.addEventListener("mousemove", function () {
    mouseMoves++;

    if (mouseDisplay) {
        mouseDisplay.innerText = mouseMoves + " moves";
    }
});

// Click tracking
document.addEventListener("click", function () {
    clicks++;
});

// Typing tracking
let captchaInput = document.getElementById("captchaInput");

if (captchaInput) {
    captchaInput.addEventListener("focus", function () {
        typingStart = Date.now();
    });

    captchaInput.addEventListener("keyup", function () {
        typingTime = Date.now() - typingStart;
    });
}

// 🔥 Live timer
setInterval(function () {
    let timeSpent = Date.now() - pageStart;

    if (timeDisplay) {
        timeDisplay.innerText = timeSpent + " ms";
    }
}, 200);

// Submit tracking
let form = document.getElementById("captchaForm");

if (form) {
    form.addEventListener("submit", function () {

        let timeSpent = Date.now() - pageStart;

        function addHidden(name, value) {
            let field = document.createElement("input");
            field.type = "hidden";
            field.name = name;
            field.value = value;
            form.appendChild(field);
        }

        addHidden("mouse_moves", mouseMoves);
        addHidden("clicks", clicks);
        addHidden("typing_time", typingTime);
        addHidden("time_spent", timeSpent);
    });
}