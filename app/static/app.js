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
    datasets: [],
    currentDatasetId: null,
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
  const datasetSelect = document.getElementById("dataset-select");

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
    await refreshDatasetList();
    await Promise.all([refreshEndUsers(), refreshConnectionNames(), refreshAdminUsers()]);
    await refreshCurrentDataset();
  }

  async function refreshAdminUsers() {
    // Only present in the DOM for the master admin (see admin.html's role check).
    const list = document.getElementById("admin-user-list");
    if (!list) return;
    const admins = await api("GET", "/admin/admins").catch(() => []);
    list.innerHTML = "";
    for (const a of admins) {
      const li = document.createElement("li");
      li.textContent = a.username + " ";
      const del = document.createElement("button");
      del.type = "button";
      del.textContent = "Remove";
      del.addEventListener("click", async () => {
        await api("DELETE", `/admin/admins/${a.id}`);
        await refreshAdminUsers();
      });
      li.appendChild(del);
      list.appendChild(li);
    }
  }

  async function refreshDatasetList() {
    state.datasets = await api("GET", "/admin/datasets").catch(() => []);

    if (state.currentDatasetId && !state.datasets.some((d) => d.id === state.currentDatasetId)) {
      state.currentDatasetId = null;
    }
    if (!state.currentDatasetId && state.datasets.length) {
      state.currentDatasetId = state.datasets[0].id;
    }

    datasetSelect.innerHTML = "";
    if (!state.datasets.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "— no datasets yet —";
      datasetSelect.appendChild(opt);
    }
    for (const ds of state.datasets) {
      const opt = document.createElement("option");
      opt.value = ds.id;
      opt.textContent = `${ds.label} (${ds.row_count} rows, ${ds.column_count} cols)`;
      if (ds.id === state.currentDatasetId) opt.selected = true;
      datasetSelect.appendChild(opt);
    }

    const list = document.getElementById("dataset-list");
    list.innerHTML = "";
    for (const ds of state.datasets) {
      const li = document.createElement("li");
      li.textContent = `${ds.label} — target table: ${ds.target_table_name || "(not set)"}`;
      list.appendChild(li);
    }
  }

  async function refreshConnectionNames() {
    const result = await api("GET", "/admin/db-connections").catch(() => ({ names: [] }));
    const select = document.getElementById("db-conn-select");
    select.innerHTML = "";
    const noneOpt = document.createElement("option");
    noneOpt.value = "";
    noneOpt.textContent = result.names.length ? "— none selected —" : "— none configured —";
    select.appendChild(noneOpt);
    for (const name of result.names) {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      select.appendChild(opt);
    }
  }

  async function refreshCurrentDataset() {
    const id = state.currentDatasetId;
    if (!id) {
      state.columns = [];
      state.rows = [];
      state.exposedIds = new Set();
      state.cellRules = {};
      state.targetTable = null;
      document.getElementById("target-table-name").value = "";
      state.selectedRows.clear();
      renderAdminColumnList();
      renderBulkAssignSelect();
      renderRawTable();
      updateBulkSelectedCount();
      applyRawTableFilter();
      return;
    }

    const [dataset, exposed, rules, target] = await Promise.all([
      api("GET", `/admin/datasets/${id}`).catch(() => null),
      api("GET", `/admin/datasets/${id}/exposed-columns`).catch(() => []),
      api("GET", `/admin/datasets/${id}/cell-rules`).catch(() => []),
      api("GET", `/admin/datasets/${id}/target-table`).catch(() => ({ table_name: null })),
    ]);

    state.columns = dataset ? dataset.columns : [];
    state.rows = dataset ? dataset.rows : [];
    state.exposedIds = new Set(exposed.map((e) => e.column_def_id));
    state.cellRules = {};
    for (const r of rules) state.cellRules[ruleKey(r.row_index, r.column_def_id)] = r.options;
    state.targetTable = target.table_name;

    document.getElementById("target-table-name").value = state.targetTable || "";
    state.selectedRows.clear();
    renderAdminColumnList();
    renderBulkAssignSelect();
    renderRawTable();
    updateBulkSelectedCount();
    applyRawTableFilter();
  }

  async function refreshEndUsers() {
    state.endUsers = await api("GET", "/admin/endusers").catch(() => []);
    renderEndUsers();
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
          await api("DELETE", `/admin/datasets/${state.currentDatasetId}/columns/${col.id}`);
          await refreshCurrentDataset();
        } catch (err) {
          window.alert(err.message);
        }
      });
      li.appendChild(del);
      list.appendChild(li);
    }
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
        await refreshEndUsers();
        renderBulkAssignSelect();
        renderRawTable();
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

  function renderRawTable() {
    rawTableWrap.innerHTML = "";
    if (!state.currentDatasetId) {
      rawTableWrap.textContent = "No dataset selected. Ingest one above.";
      return;
    }
    if (!state.columns.length) {
      rawTableWrap.textContent = "This dataset has no columns.";
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
      rowTh.textContent = row.is_admin_added ? `${row.row_index} (new)` : row.row_index;
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
        await api("PUT", `/admin/datasets/${state.currentDatasetId}/rows/${row.row_index}/assign`, { enduser_id });
      });
      assignTd.appendChild(select);
      tr.appendChild(assignTd);

      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    rawTableWrap.appendChild(table);
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
      await api("PUT", `/admin/datasets/${state.currentDatasetId}/exposed-columns`, { column_def_ids: selected });
      ingestStatus.textContent = "Exposed columns updated.";
      await refreshCurrentDataset();
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
        await api("DELETE", `/admin/datasets/${state.currentDatasetId}/cell-rules/${row.row_index}/${col.id}`);
      } else {
        await api("PUT", `/admin/datasets/${state.currentDatasetId}/cell-rules/${row.row_index}/${col.id}`, {
          options,
        });
      }
      await refreshCurrentDataset();
    } catch (err) {
      window.alert(err.message);
    }
  }

  datasetSelect.addEventListener("change", async () => {
    state.currentDatasetId = datasetSelect.value ? parseInt(datasetSelect.value, 10) : null;
    await refreshCurrentDataset();
  });

  document.getElementById("admin-column-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!state.currentDatasetId) return;
    const name = document.getElementById("admin-column-name").value;
    const input_type = columnTypeSelect.value;
    const optionsRaw = document.getElementById("admin-column-options").value;
    const options =
      input_type === "dropdown"
        ? optionsRaw.split(",").map((s) => s.trim()).filter((s) => s.length > 0)
        : null;
    try {
      await api("POST", `/admin/datasets/${state.currentDatasetId}/columns`, { name, input_type, options });
      document.getElementById("admin-column-form").reset();
      toggleColumnOptionsField();
      await refreshCurrentDataset();
    } catch (err) {
      window.alert(err.message);
    }
  });

  document.getElementById("add-row-btn").addEventListener("click", async () => {
    if (!state.currentDatasetId) return;
    try {
      await api("POST", `/admin/datasets/${state.currentDatasetId}/rows`, {});
      await refreshCurrentDataset();
    } catch (err) {
      window.alert(err.message);
    }
  });

  document.getElementById("bulk-assign-btn").addEventListener("click", async () => {
    if (!state.currentDatasetId) return;
    const rowIndices = Array.from(state.selectedRows);
    if (rowIndices.length === 0) {
      ingestStatus.textContent = "Select at least one row to share.";
      return;
    }
    const enduser_id = bulkAssignSelect.value ? parseInt(bulkAssignSelect.value, 10) : null;
    try {
      const result = await api("PUT", `/admin/datasets/${state.currentDatasetId}/rows/assign-bulk`, {
        row_indices: rowIndices,
        enduser_id,
      });
      ingestStatus.textContent = `Shared ${result.updated} row(s).`;
      await refreshCurrentDataset();
    } catch (err) {
      ingestStatus.textContent = err.message;
    }
  });

  document.getElementById("xlsx-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const file = document.getElementById("xlsx-file").files[0];
    if (!file) return;
    const label = document.getElementById("xlsx-label").value;
    const form = new FormData();
    form.append("file", file);
    const url = "/admin/ingest/xlsx" + (label ? `?label=${encodeURIComponent(label)}` : "");
    ingestStatus.textContent = "Ingesting...";
    try {
      const result = await api("POST", url, form);
      ingestStatus.textContent = `Ingested "${result.label}": ${result.row_count} rows, ${result.columns.length} columns.`;
      state.currentDatasetId = result.dataset_id;
      document.getElementById("xlsx-form").reset();
      await refreshAll();
    } catch (err) {
      ingestStatus.textContent = err.message;
    }
  });

  document.getElementById("db-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const connSelect = document.getElementById("db-conn-select").value;
    const connRaw = document.getElementById("db-conn").value;
    const connection = connSelect || connRaw;
    const table_name = document.getElementById("db-table").value;
    const label = document.getElementById("db-label").value || null;
    ingestStatus.textContent = "Ingesting...";
    try {
      const result = await api("POST", "/admin/ingest/db", { connection, table_name, label });
      ingestStatus.textContent = `Ingested "${result.label}": ${result.row_count} rows, ${result.columns.length} columns.`;
      state.currentDatasetId = result.dataset_id;
      document.getElementById("db-form").reset();
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
      await refreshEndUsers();
      renderBulkAssignSelect();
      renderRawTable();
    } catch (err) {
      window.alert(err.message);
    }
  });

  const adminUserForm = document.getElementById("admin-user-form");
  if (adminUserForm) {
    adminUserForm.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const username = document.getElementById("admin-user-username").value;
      const password = document.getElementById("admin-user-password").value;
      try {
        await api("POST", "/admin/admins", { username, password });
        adminUserForm.reset();
        await refreshAdminUsers();
      } catch (err) {
        window.alert(err.message);
      }
    });
  }

  document.getElementById("target-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!state.currentDatasetId) return;
    const table_name = document.getElementById("target-table-name").value;
    try {
      await api("PUT", `/admin/datasets/${state.currentDatasetId}/target-table`, { table_name });
      targetStatus.textContent = "Target table saved.";
      await refreshDatasetList();
    } catch (err) {
      targetStatus.textContent = err.message;
    }
  });

  document.getElementById("ship-btn").addEventListener("click", async () => {
    if (!state.currentDatasetId) return;
    try {
      const result = await api("POST", `/admin/datasets/${state.currentDatasetId}/ship`, {});
      targetStatus.textContent = `Shipped ${result.row_count} rows to "${result.table_name}".`;
    } catch (err) {
      targetStatus.textContent = err.message;
    }
  });

  document.getElementById("metadata-btn").addEventListener("click", async () => {
    const out = document.getElementById("metadata-out");
    if (!state.currentDatasetId) {
      out.textContent = "No dataset selected.";
      return;
    }
    try {
      const meta = await api("GET", `/admin/datasets/${state.currentDatasetId}/metadata`);
      out.textContent = JSON.stringify(meta, null, 2);
    } catch (err) {
      out.textContent = err.message;
    }
  });

  refreshAll();
}

/* ---------------- Review page ---------------- */

function initReviewPage() {
  let datasets = [];
  const pageStatus = document.getElementById("page-status");
  const wrap = document.getElementById("grid-wrap");
  const applyGridFilter = attachSearchFilter(document.getElementById("grid-search"), wrap);

  async function loadGrid() {
    try {
      const grid = await api("GET", "/review/grid");
      datasets = grid.datasets;
      pageStatus.textContent = "";
    } catch (err) {
      pageStatus.textContent = err.message;
      datasets = [];
    }
    renderAll();
    applyGridFilter();
  }

  async function saveOneEdit(datasetId, rowIndex, colId, value, cellStatusEl) {
    cellStatusEl.textContent = "Saving…";
    cellStatusEl.classList.remove("cell-status-error");
    try {
      await api("POST", "/review/save", {
        dataset_id: datasetId,
        edits: [{ row_index: rowIndex, column_def_id: colId, value }],
      });
      cellStatusEl.textContent = "Saved";
    } catch (err) {
      cellStatusEl.textContent = err.message;
      cellStatusEl.classList.add("cell-status-error");
    }
  }

  async function shipDataset(datasetId, shipStatusEl) {
    shipStatusEl.textContent = "Shipping…";
    try {
      const result = await api("POST", `/review/datasets/${datasetId}/ship`, {});
      shipStatusEl.textContent = `Shipped ${result.row_count} rows to "${result.table_name}".`;
    } catch (err) {
      shipStatusEl.textContent = err.message;
    }
  }

  function renderAll() {
    wrap.innerHTML = "";
    if (!datasets.length) {
      wrap.textContent = "No rows assigned to you yet.";
      return;
    }
    for (const ds of datasets) {
      wrap.appendChild(renderDatasetSection(ds));
    }
  }

  function renderDatasetSection(ds) {
    const section = document.createElement("div");
    section.className = "dataset-section";

    const heading = document.createElement("h3");
    heading.textContent = ds.label;
    section.appendChild(heading);

    const columns = [...ds.columns].sort((a, b) => a.order - b.order);
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
    for (const row of ds.rows) {
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
            const debouncedSave = debounce(
              () => saveOneEdit(ds.dataset_id, row.row_index, col.column_def_id, input.value, cellStatusEl),
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
            select.addEventListener("change", () =>
              saveOneEdit(ds.dataset_id, row.row_index, col.column_def_id, select.value, cellStatusEl)
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
    section.appendChild(table);

    const shipBtn = document.createElement("button");
    shipBtn.type = "button";
    shipBtn.textContent = "Ship to DB";
    const shipStatus = document.createElement("span");
    shipStatus.className = "status";
    shipBtn.addEventListener("click", () => shipDataset(ds.dataset_id, shipStatus));
    section.appendChild(shipBtn);
    section.appendChild(shipStatus);

    return section;
  }

  loadGrid();
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("raw-table-wrap")) initAdminPage();
  if (document.getElementById("grid-wrap")) initReviewPage();
});
