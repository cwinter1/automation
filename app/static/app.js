async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body instanceof FormData) {
    opts.body = body;
  } else if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data);
    } catch (e) {
      /* ignore parse failure, keep statusText */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

function debounce(fn, delayMs) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delayMs);
  };
}

/* Wires a <input type=search> to filter a table's <tbody> rows by substring match
   against the row's visible text. Re-apply after each re-render via applyFilter(). */
function attachSearchFilter(inputEl, wrapEl) {
  const applyFilter = () => {
    const term = inputEl.value.trim().toLowerCase();
    const rows = wrapEl.querySelectorAll("tbody tr");
    rows.forEach((tr) => {
      const text = tr.textContent.toLowerCase();
      tr.style.display = !term || text.includes(term) ? "" : "none";
    });
  };
  inputEl.addEventListener("input", applyFilter);
  return applyFilter;
}

/* ---------------- Admin page ---------------- */

function initAdminPage() {
  const state = {
    columns: [],
    rows: [],
    exposedIds: new Set(),
    cellRules: {},
    endUsers: [],
    targetTable: null,
    selectedRows: new Set(),
  };

  const ingestStatus = document.getElementById("ingest-status");
  const targetStatus = document.getElementById("target-status");
  const bulkSelectedCount = document.getElementById("bulk-selected-count");
  const bulkAssignSelect = document.getElementById("bulk-assign-select");

  const rawTableWrap = document.getElementById("raw-table-wrap");
  const applyRawTableFilter = attachSearchFilter(document.getElementById("raw-table-search"), rawTableWrap);

  const columnTypeSelect = document.getElementById("admin-column-type");
  const columnOptionsWrap = document.getElementById("admin-column-options-wrap");
  const toggleColumnOptionsField = () => {
    columnOptionsWrap.style.display = columnTypeSelect.value === "dropdown" ? "" : "none";
  };
  columnTypeSelect.addEventListener("change", toggleColumnOptionsField);
  toggleColumnOptionsField();

  function ruleKey(rowIndex, colId) {
    return `${rowIndex}:${colId}`;
  }

  async function refreshAll() {
    const [dataset, exposed, rules, endUsers, target] = await Promise.all([
      api("GET", "/admin/dataset").catch(() => null),
      api("GET", "/admin/exposed-columns").catch(() => []),
      api("GET", "/admin/cell-rules").catch(() => []),
      api("GET", "/admin/endusers").catch(() => []),
      api("GET", "/admin/target-table").catch(() => ({ table_name: null })),
    ]);

    state.columns = dataset ? dataset.columns : [];
    state.rows = dataset ? dataset.rows : [];
    state.exposedIds = new Set(exposed.map((e) => e.column_def_id));
    state.cellRules = {};
    for (const r of rules) state.cellRules[ruleKey(r.row_index, r.column_def_id)] = r.options;
    state.endUsers = endUsers;
    state.targetTable = target.table_name;

    document.getElementById("target-table-name").value = state.targetTable || "";
    state.selectedRows.clear();
    renderEndUsers();
    renderAdminColumnList();
    renderBulkAssignSelect();
    renderRawTable();
    updateBulkSelectedCount();
    applyRawTableFilter();
  }

  function renderAdminColumnList() {
    const list = document.getElementById("admin-column-list");
    list.innerHTML = "";
    for (const col of state.columns.filter((c) => c.is_admin_added)) {
      const li = document.createElement("li");
      const typeLabel = col.input_type === "dropdown" ? `dropdown: ${(col.options || []).join(", ")}` : "free text";
      li.textContent = `${col.source_name} (${typeLabel}) `;
      const del = document.createElement("button");
      del.type = "button";
      del.textContent = "Remove";
      del.addEventListener("click", async () => {
        try {
          await api("DELETE", `/admin/columns/${col.id}`);
          await refreshAll();
        } catch (err) {
          window.alert(err.message);
        }
      });
      li.appendChild(del);
      list.appendChild(li);
    }
  }

  function renderBulkAssignSelect() {
    bulkAssignSelect.innerHTML = "";
    const noneOpt = document.createElement("option");
    noneOpt.value = "";
    noneOpt.textContent = "— unassigned —";
    bulkAssignSelect.appendChild(noneOpt);
    for (const u of state.endUsers) {
      const opt = document.createElement("option");
      opt.value = u.id;
      opt.textContent = u.username;
      bulkAssignSelect.appendChild(opt);
    }
  }

  function updateBulkSelectedCount() {
    const n = state.selectedRows.size;
    bulkSelectedCount.textContent = `${n} row${n === 1 ? "" : "s"} selected`;
  }

  function renderEndUsers() {
    const list = document.getElementById("enduser-list");
    list.innerHTML = "";
    for (const u of state.endUsers) {
      const li = document.createElement("li");
      li.textContent = u.username + " ";
      const del = document.createElement("button");
      del.type = "button";
      del.textContent = "Remove";
      del.addEventListener("click", async () => {
        await api("DELETE", `/admin/endusers/${u.id}`);
        await refreshAll();
      });
      li.appendChild(del);
      list.appendChild(li);
    }
  }

  function renderRawTable() {
    const wrap = document.getElementById("raw-table-wrap");
    wrap.innerHTML = "";
    if (!state.columns.length) {
      wrap.textContent = "No dataset ingested yet.";
      return;
    }

    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");

    const selectTh = document.createElement("th");
    headRow.appendChild(selectTh);

    const cornerTh = document.createElement("th");
    cornerTh.textContent = "Row";
    headRow.appendChild(cornerTh);

    for (const col of state.columns) {
      const th = document.createElement("th");
      if (col.is_admin_added) {
        th.classList.add("admin-col-header");
        th.textContent = `${col.source_name} (custom)`;
      } else {
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.dataset.colId = col.id;
        checkbox.checked = state.exposedIds.has(col.id);
        checkbox.addEventListener("change", () => onColumnToggle());
        th.appendChild(checkbox);
        th.appendChild(document.createTextNode(" " + col.source_name));
      }
      headRow.appendChild(th);
    }
    const assignTh = document.createElement("th");
    assignTh.textContent = "Assign to";
    headRow.appendChild(assignTh);

    thead.appendChild(headRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    for (const row of state.rows) {
      const tr = document.createElement("tr");

      const selectTd = document.createElement("td");
      const selectCheckbox = document.createElement("input");
      selectCheckbox.type = "checkbox";
      selectCheckbox.checked = state.selectedRows.has(row.row_index);
      selectCheckbox.addEventListener("change", () => {
        if (selectCheckbox.checked) {
          state.selectedRows.add(row.row_index);
        } else {
          state.selectedRows.delete(row.row_index);
        }
        updateBulkSelectedCount();
      });
      selectTd.appendChild(selectCheckbox);
      tr.appendChild(selectTd);

      const rowTh = document.createElement("th");
      rowTh.textContent = row.row_index;
      tr.appendChild(rowTh);

      for (const col of state.columns) {
        const td = document.createElement("td");
        const value = row.values[col.safe_name];
        td.textContent = value === null || value === undefined ? "" : value;

        if (col.is_admin_added) {
          td.classList.add("admin-col-cell");
          td.title = "Filled in by end users — always editable, no per-cell flagging needed";
        } else {
          const exposed = state.exposedIds.has(col.id);
          const flagged = ruleKey(row.row_index, col.id) in state.cellRules;
          if (exposed) {
            td.classList.add("flaggable");
            if (flagged) td.classList.add("flagged");
            td.title = "Click to flag/edit correction options";
            td.addEventListener("click", () => onCellClick(row, col));
          }
        }
        tr.appendChild(td);
      }

      const assignTd = document.createElement("td");
      const select = document.createElement("select");
      const noneOpt = document.createElement("option");
      noneOpt.value = "";
      noneOpt.textContent = "— unassigned —";
      select.appendChild(noneOpt);
      for (const u of state.endUsers) {
        const opt = document.createElement("option");
        opt.value = u.id;
        opt.textContent = u.username;
        if (row.assigned_enduser_id === u.id) opt.selected = true;
        select.appendChild(opt);
      }
      select.addEventListener("change", async () => {
        const enduser_id = select.value ? parseInt(select.value, 10) : null;
        await api("PUT", `/admin/rows/${row.row_index}/assign`, { enduser_id });
      });
      assignTd.appendChild(select);
      tr.appendChild(assignTd);

      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    wrap.appendChild(table);
  }

  async function onColumnToggle() {
    const checkboxes = document.querySelectorAll("#raw-table-wrap thead th input[type=checkbox]");
    const selected = [];
    checkboxes.forEach((cb) => {
      if (cb.checked) selected.push(parseInt(cb.dataset.colId, 10));
    });
    if (selected.length < 4 || selected.length > 6) {
      ingestStatus.textContent = `Select between 4 and 6 columns (currently ${selected.length}).`;
      return;
    }
    try {
      await api("PUT", "/admin/exposed-columns", { column_def_ids: selected });
      ingestStatus.textContent = "Exposed columns updated.";
      await refreshAll();
    } catch (err) {
      ingestStatus.textContent = err.message;
    }
  }

  async function onCellClick(row, col) {
    const existing = state.cellRules[ruleKey(row.row_index, col.id)] || [];
    const input = window.prompt(
      `Correction options for row ${row.row_index}, column "${col.source_name}" (comma-separated). Leave blank to unflag.`,
      existing.join(", ")
    );
    if (input === null) return;

    const options = input
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);

    try {
      if (options.length === 0) {
        await api("DELETE", `/admin/cell-rules/${row.row_index}/${col.id}`);
      } else {
        await api("PUT", `/admin/cell-rules/${row.row_index}/${col.id}`, { options });
      }
      await refreshAll();
    } catch (err) {
      window.alert(err.message);
    }
  }

  document.getElementById("admin-column-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const name = document.getElementById("admin-column-name").value;
    const input_type = columnTypeSelect.value;
    const optionsRaw = document.getElementById("admin-column-options").value;
    const options =
      input_type === "dropdown"
        ? optionsRaw.split(",").map((s) => s.trim()).filter((s) => s.length > 0)
        : null;
    try {
      await api("POST", "/admin/columns", { name, input_type, options });
      document.getElementById("admin-column-form").reset();
      toggleColumnOptionsField();
      await refreshAll();
    } catch (err) {
      window.alert(err.message);
    }
  });

  document.getElementById("bulk-assign-btn").addEventListener("click", async () => {
    const rowIndices = Array.from(state.selectedRows);
    if (rowIndices.length === 0) {
      ingestStatus.textContent = "Select at least one row to share.";
      return;
    }
    const enduser_id = bulkAssignSelect.value ? parseInt(bulkAssignSelect.value, 10) : null;
    try {
      const result = await api("PUT", "/admin/rows/assign-bulk", { row_indices: rowIndices, enduser_id });
      ingestStatus.textContent = `Shared ${result.updated} row(s).`;
      await refreshAll();
    } catch (err) {
      ingestStatus.textContent = err.message;
    }
  });

  document.getElementById("xlsx-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const file = document.getElementById("xlsx-file").files[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    ingestStatus.textContent = "Ingesting...";
    try {
      const result = await api("POST", "/admin/ingest/xlsx", form);
      ingestStatus.textContent = `Ingested ${result.row_count} rows, ${result.columns.length} columns.`;
      await refreshAll();
    } catch (err) {
      ingestStatus.textContent = err.message;
    }
  });

  document.getElementById("db-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const connection_string = document.getElementById("db-conn").value;
    const table_name = document.getElementById("db-table").value;
    ingestStatus.textContent = "Ingesting...";
    try {
      const result = await api("POST", "/admin/ingest/db", { connection_string, table_name });
      ingestStatus.textContent = `Ingested ${result.row_count} rows, ${result.columns.length} columns.`;
      await refreshAll();
    } catch (err) {
      ingestStatus.textContent = err.message;
    }
  });

  document.getElementById("enduser-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const username = document.getElementById("enduser-username").value;
    const password = document.getElementById("enduser-password").value;
    try {
      await api("POST", "/admin/endusers", { username, password });
      document.getElementById("enduser-form").reset();
      await refreshAll();
    } catch (err) {
      window.alert(err.message);
    }
  });

  document.getElementById("target-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const table_name = document.getElementById("target-table-name").value;
    try {
      await api("PUT", "/admin/target-table", { table_name });
      targetStatus.textContent = "Target table saved.";
    } catch (err) {
      targetStatus.textContent = err.message;
    }
  });

  refreshAll();
}

/* ---------------- Review page ---------------- */

function initReviewPage() {
  let grid = { columns: [], rows: [] };
  const status = document.getElementById("save-status");
  const wrap = document.getElementById("grid-wrap");
  const applyGridFilter = attachSearchFilter(document.getElementById("grid-search"), wrap);

  async function loadGrid() {
    try {
      grid = await api("GET", "/review/grid");
      status.textContent = "";
    } catch (err) {
      status.textContent = err.message;
      grid = { columns: [], rows: [] };
    }
    renderGrid();
    applyGridFilter();
  }

  async function saveOneEdit(rowIndex, colId, value, cellStatusEl) {
    cellStatusEl.textContent = "Saving…";
    cellStatusEl.classList.remove("cell-status-error");
    try {
      await api("POST", "/review/save", {
        edits: [{ row_index: rowIndex, column_def_id: colId, value }],
      });
      cellStatusEl.textContent = "Saved";
    } catch (err) {
      cellStatusEl.textContent = err.message;
      cellStatusEl.classList.add("cell-status-error");
    }
  }

  function renderGrid() {
    wrap.innerHTML = "";
    if (!grid.rows.length) {
      wrap.textContent = "No rows assigned to you yet.";
      return;
    }

    const columns = [...grid.columns].sort((a, b) => a.order - b.order);
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    for (const col of columns) {
      const th = document.createElement("th");
      th.textContent = col.label;
      headRow.appendChild(th);
    }
    thead.appendChild(headRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    for (const row of grid.rows) {
      const tr = document.createElement("tr");
      for (const col of columns) {
        const cell = row.cells.find((c) => c.column_def_id === col.column_def_id);
        const td = document.createElement("td");
        if (cell.editable) {
          const cellStatusEl = document.createElement("span");
          cellStatusEl.className = "cell-status";

          if (cell.input_type === "text") {
            const input = document.createElement("input");
            input.type = "text";
            input.value = cell.value === null || cell.value === undefined ? "" : cell.value;
            input.dataset.row = row.row_index;
            input.dataset.col = col.column_def_id;
            const debouncedSave = debounce(
              () => saveOneEdit(row.row_index, col.column_def_id, input.value, cellStatusEl),
              500
            );
            input.addEventListener("input", () => {
              cellStatusEl.textContent = "";
              debouncedSave();
            });
            td.appendChild(input);
          } else {
            const select = document.createElement("select");
            for (const opt of cell.options || []) {
              const optionEl = document.createElement("option");
              optionEl.value = opt;
              optionEl.textContent = opt;
              if (opt === cell.value) optionEl.selected = true;
              select.appendChild(optionEl);
            }
            select.dataset.row = row.row_index;
            select.dataset.col = col.column_def_id;
            select.addEventListener("change", () =>
              saveOneEdit(row.row_index, col.column_def_id, select.value, cellStatusEl)
            );
            td.appendChild(select);
          }
          td.appendChild(cellStatusEl);
        } else {
          td.textContent = cell.value === null || cell.value === undefined ? "" : cell.value;
        }
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    wrap.appendChild(table);
  }

  document.getElementById("save-btn").addEventListener("click", async () => {
    const inputs = document.querySelectorAll("#grid-wrap select, #grid-wrap input[type=text]");
    const edits = Array.from(inputs).map((el) => ({
      row_index: parseInt(el.dataset.row, 10),
      column_def_id: parseInt(el.dataset.col, 10),
      value: el.value,
    }));
    try {
      const result = await api("POST", "/review/save", { edits });
      status.textContent = `Saved ${result.row_count} rows to "${result.table_name}".`;
    } catch (err) {
      status.textContent = err.message;
    }
  });

  loadGrid();
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("raw-table-wrap")) initAdminPage();
  if (document.getElementById("grid-wrap")) initReviewPage();
});
