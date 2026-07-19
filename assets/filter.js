// Progressive-enhancement client-side filtering for browse tables.
// Every row's full data is already in the server-rendered HTML (crawlers and
// no-JS visitors see the complete unfiltered table); this only hides rows.
(function () {
  function initTableFilters(opts) {
    var table = document.getElementById(opts.table);
    var filters = document.getElementById(opts.filters);
    var countEl = document.getElementById(opts.count);
    if (!table || !filters) return;
    var rows = Array.prototype.slice.call(table.tBodies[0].rows);
    var controls = Array.prototype.slice.call(filters.querySelectorAll("[data-filter-field]"));

    function matches(row, field, mode, value) {
      var raw = row.getAttribute("data-" + field) || "";
      if (mode === "includes") {
        return ("," + raw + ",").indexOf("," + value + ",") !== -1;
      }
      return raw === value;
    }

    function apply() {
      var active = controls
        .map(function (c) {
          return {
            field: c.getAttribute("data-filter-field"),
            mode: c.getAttribute("data-filter-mode") || "equals",
            value: c.value
          };
        })
        .filter(function (f) { return f.value; });

      var visible = 0;
      rows.forEach(function (row) {
        var ok = active.every(function (f) { return matches(row, f.field, f.mode, f.value); });
        row.style.display = ok ? "" : "none";
        if (ok) visible++;
      });
      if (countEl) {
        countEl.textContent = active.length
          ? visible + " of " + rows.length + " " + opts.label
          : rows.length + " " + opts.label;
      }
    }

    controls.forEach(function (c) { c.addEventListener("change", apply); });
    var resetBtn = filters.querySelector("[data-filter-reset]");
    if (resetBtn) {
      resetBtn.addEventListener("click", function () {
        controls.forEach(function (c) { c.value = ""; });
        apply();
      });
    }
  }
  window.initTableFilters = initTableFilters;
})();
