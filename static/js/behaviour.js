let mouseMoves = 0;
let clicks = 0;
let typingStart = 0;
let typingTime = 0;
let pageStart = Date.now();

document.addEventListener("mousemove", function () {
  mouseMoves++;
});

document.addEventListener("click", function () {
  clicks++;
});

let captchaInput = document.getElementById("captchaInput");

captchaInput.addEventListener("focus", function () {
  typingStart = Date.now();
});

captchaInput.addEventListener("keyup", function () {
  typingTime = Date.now() - typingStart;
});

document.getElementById("captchaForm").addEventListener("submit", function () {

  let timeSpent = Date.now() - pageStart;

  function addHidden(name, value) {
    let field = document.createElement("input");
    field.type = "hidden";
    field.name = name;
    field.value = value;
    document.getElementById("captchaForm").appendChild(field);
  }

  addHidden("mouse_moves", mouseMoves);
  addHidden("clicks", clicks);
  addHidden("typing_time", typingTime);
  addHidden("time_spent", timeSpent);

});