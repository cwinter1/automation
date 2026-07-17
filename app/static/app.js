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
    renderBulkAssignSelect();
    renderRawTable();
    updateBulkSelectedCount();
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
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = state.exposedIds.has(col.id);
      checkbox.addEventListener("change", () => onColumnToggle());
      th.appendChild(checkbox);
      th.appendChild(document.createTextNode(" " + col.source_name));
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

        const exposed = state.exposedIds.has(col.id);
        const flagged = ruleKey(row.row_index, col.id) in state.cellRules;
        if (exposed) {
          td.classList.add("flaggable");
          if (flagged) td.classList.add("flagged");
          td.title = "Click to flag/edit correction options";
          td.addEventListener("click", () => onCellClick(row, col));
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
    checkboxes.forEach((cb, idx) => {
      if (cb.checked) selected.push(state.columns[idx].id);
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

  async function loadGrid() {
    const status = document.getElementById("save-status");
    try {
      grid = await api("GET", "/review/grid");
      status.textContent = "";
    } catch (err) {
      status.textContent = err.message;
      grid = { columns: [], rows: [] };
    }
    renderGrid();
  }

  function renderGrid() {
    const wrap = document.getElementById("grid-wrap");
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
          const select = document.createElement("select");
          select.dataset.row = row.row_index;
          select.dataset.col = col.column_def_id;
          for (const opt of cell.options) {
            const optionEl = document.createElement("option");
            optionEl.value = opt;
            optionEl.textContent = opt;
            if (opt === cell.value) optionEl.selected = true;
            select.appendChild(optionEl);
          }
          td.appendChild(select);
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
    const status = document.getElementById("save-status");
    const selects = document.querySelectorAll("#grid-wrap select");
    const edits = Array.from(selects).map((sel) => ({
      row_index: parseInt(sel.dataset.row, 10),
      column_def_id: parseInt(sel.dataset.col, 10),
      value: sel.value,
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
