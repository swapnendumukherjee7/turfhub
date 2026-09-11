// TurfHub prototype — small progressive-enhancement helpers.
// No frameworks: this keeps the prototype easy to read and demo.

document.addEventListener("DOMContentLoaded", function () {
  // --- Slot picker (turf detail page) ---------------------------------
  var slotButtons = document.querySelectorAll(".slot.available");
  var slotInput = document.getElementById("selected-slot");
  var bookBtn = document.getElementById("book-now-btn");
  slotButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      slotButtons.forEach(function (b) { b.classList.remove("selected"); });
      btn.classList.add("selected");
      if (slotInput) slotInput.value = btn.dataset.slot;
      if (bookBtn) {
        var url = new URL(bookBtn.href, window.location.origin);
        url.searchParams.set("slot", btn.dataset.slot);
        bookBtn.href = url.toString();
        bookBtn.removeAttribute("disabled");
      }
    });
  });

  // --- Compare selection cap (find page) -------------------------------
  var compareBoxes = document.querySelectorAll(".compare-check input[type=checkbox]");
  var compareBar = document.getElementById("compare-bar");
  var compareLink = document.getElementById("compare-link");
  var compareCount = document.getElementById("compare-count");

  function refreshCompareBar() {
    var checked = Array.from(compareBoxes).filter(function (c) { return c.checked; });
    if (!compareBar) return;
    if (checked.length > 0) {
      compareBar.classList.add("visible");
      compareCount.textContent = checked.length;
      var ids = checked.map(function (c) { return c.value; }).join(",");
      compareLink.href = "/compare?ids=" + ids;
    } else {
      compareBar.classList.remove("visible");
    }
    compareBoxes.forEach(function (c) {
      c.disabled = !c.checked && checked.length >= 3;
    });
  }

  compareBoxes.forEach(function (box) {
    box.addEventListener("change", refreshCompareBar);
  });
  refreshCompareBar();

  // --- Availability grid quick action (manager) -------------------------
  document.querySelectorAll(".slot-form-trigger").forEach(function (el) {
    el.addEventListener("click", function () {
      el.closest("form").submit();
    });
  });
});
