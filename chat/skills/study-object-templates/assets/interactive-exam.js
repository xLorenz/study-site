/**
 * interactive-exam.js — canonical toggle-answer handler for Template 7.
 * Copy verbatim into <script> at the bottom of the HTML.
 * Each exercise gets a unique answer box id (ans1, ans2, …) whose sibling
 * button carries onclick="toggleAnswer('ansN')".
 */
function toggleAnswer(id){
  const box = document.getElementById(id);
  const btn = box.previousElementSibling;
  box.classList.toggle('visible');
  btn.classList.toggle('showing');
  btn.textContent = box.classList.contains('visible')
    ? 'Hide answer'
    : 'Show answer';
}