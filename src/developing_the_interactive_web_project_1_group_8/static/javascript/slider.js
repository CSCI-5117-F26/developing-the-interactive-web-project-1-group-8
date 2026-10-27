//  Code from tutorial at https://codingartistweb.com/2021/06/double-range-slider-html-css-javascript/ and customized.
window.onload = function () {
  slideOne();
  slideTwo();
};
let sliderOne = document.getElementById("players-1");
let sliderTwo = document.getElementById("players-2");
let displayValOne = document.getElementById("range1");
let displayValTwo = document.getElementById("range2");
let minGap = 0;
let sliderTrack = document.querySelector(".slider-track");
let sliderMaxValue = Number(document.getElementById("players-1").max);
let sliderMinValue = Number(document.getElementById("players-1").min);
function slideOne() {
  if (parseInt(sliderTwo.value) - parseInt(sliderOne.value) <= minGap) {
    sliderOne.value = parseInt(sliderTwo.value) - minGap;
  }
  displayValOne.textContent = sliderOne.value;
  fillColor();
}
function slideTwo() {
  if (parseInt(sliderTwo.value) - parseInt(sliderOne.value) <= minGap) {
    sliderTwo.value = parseInt(sliderOne.value) + minGap;
  }
  displayValTwo.textContent = sliderTwo.value;
  fillColor();
}
function fillColor() {
  let percent1 =
    ((sliderOne.value - sliderMinValue) / (sliderMaxValue - sliderMinValue)) *
    100;
  let percent2 =
    ((sliderTwo.value - sliderMinValue) / (sliderMaxValue - sliderMinValue)) *
    100;
  sliderTrack.style.background = `linear-gradient(to right, #dadae5 ${percent1}% , var(--color-primary) ${percent1}% , var(--color-primary) ${percent2}%, #dadae5 ${percent2}%)`;
}
