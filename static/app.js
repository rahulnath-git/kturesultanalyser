const state = {
  gradeConfig: [],
  batches: [],
  activeBatchId: null,
  activeBatch: null,
  departmentFilter: "All Departments",
  selectedFile: null,
  activeTab: "home",
  activeResultTab: "overview",
};

const elements = {
  dropZone: document.querySelector("#dropZone"),
  pdfFileInput: document.querySelector("#pdfFileInput"),
  browseButton: document.querySelector("#browseButton"),
  selectedFileLabel: document.querySelector("#selectedFileLabel"),
  batchNameInput: document.querySelector("#batchNameInput"),
  uploadButton: document.querySelector("#uploadButton"),
  addGradeButton: document.querySelector("#addGradeButton"),
  saveConfigButton: document.querySelector("#saveConfigButton"),
  gradeConfigBody: document.querySelector("#gradeConfigBody"),
  batchList: document.querySelector("#batchList"),
  activeBatchMeta: document.querySelector("#activeBatchMeta"),
  departmentFilter: document.querySelector("#departmentFilter"),
  refreshBatchButton: document.querySelector("#refreshBatchButton"),
  unknownGradeNotice: document.querySelector("#unknownGradeNotice"),
  summaryCards: document.querySelector("#summaryCards"),
  gpaThresholdInput: document.querySelector("#gpaThresholdInput"),
  downloadWordButton: document.querySelector("#downloadWordButton"),
  downloadRegisterExcelButton: document.querySelector(
    "#downloadRegisterExcelButton",
  ),
  topStudentsTable: document.querySelector("#topStudentsTable"),
  subjectsBody: document.querySelector("#subjectsBody"),
  saveCreditsButton: document.querySelector("#saveCreditsButton"),
  studentSearchInput: document.querySelector("#studentSearchInput"),
  studentsBody: document.querySelector("#studentsBody"),
  statusToast: document.querySelector("#statusToast"),
  navToggleButton: document.querySelector("#navToggleButton"),
  tabButtons: Array.from(document.querySelectorAll("[data-tab-target]")),
  tabPanels: Array.from(document.querySelectorAll("[data-tab-panel]")),
  resultTabButtons: Array.from(
    document.querySelectorAll("[data-result-tab-target]"),
  ),
  resultPanels: Array.from(document.querySelectorAll("[data-result-panel]")),
};

let toastTimer = null;

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  loadDashboard();
});

function bindEvents() {
  elements.navToggleButton.addEventListener("click", toggleNavigation);

  elements.tabButtons.forEach((button) => {
    button.addEventListener("click", () =>
      activateTab(button.dataset.tabTarget),
    );
  });
  elements.resultTabButtons.forEach((button) => {
    button.addEventListener("click", () =>
      activateResultTab(button.dataset.resultTabTarget),
    );
  });

  elements.browseButton.addEventListener("click", (event) => {
    event.stopPropagation();
    elements.pdfFileInput.click();
  });
  elements.dropZone.addEventListener("click", () =>
    elements.pdfFileInput.click(),
  );
  elements.pdfFileInput.addEventListener("change", handleFileSelection);
  elements.uploadButton.addEventListener("click", handleUpload);
  elements.addGradeButton.addEventListener("click", addGradeRow);
  elements.saveConfigButton.addEventListener("click", saveGradeConfig);
  elements.refreshBatchButton.addEventListener("click", () => {
    if (state.activeBatchId) {
      loadBatch(state.activeBatchId);
    } else {
      loadDashboard();
    }
  });
  elements.departmentFilter.addEventListener("change", () => {
    state.departmentFilter = elements.departmentFilter.value;
    renderActiveBatch();
  });
  elements.saveCreditsButton.addEventListener("click", saveCourseCredits);
  elements.studentSearchInput.addEventListener("input", renderStudentsTable);
  elements.downloadWordButton.addEventListener("click", downloadWordReport);
  elements.downloadRegisterExcelButton.addEventListener(
    "click",
    downloadRegisterExcel,
  );

  elements.batchList.addEventListener("click", async (event) => {
    const selectButton = event.target.closest('[data-action="select-batch"]');
    if (selectButton) {
      await loadBatch(Number(selectButton.dataset.batchId));
      activateTab("results");
      return;
    }

    const deleteButton = event.target.closest('[data-action="delete-batch"]');
    if (deleteButton) {
      const batchId = Number(deleteButton.dataset.batchId);
      const batch = state.batches.find((item) => item.id === batchId);
      const confirmed = window.confirm(
        `Delete batch "${batch?.name ?? batchId}"?`,
      );
      if (!confirmed) {
        return;
      }

      try {
        await apiRequest(`/api/batches/${batchId}`, { method: "DELETE" });
        showToast("Batch deleted.", "success");
        const nextBatchId =
          state.activeBatchId === batchId
            ? (state.batches.find((item) => item.id !== batchId)?.id ?? null)
            : state.activeBatchId;
        await loadDashboard(nextBatchId);
      } catch (error) {
        showToast(error.message, "error");
      }
    }
  });

  elements.gradeConfigBody.addEventListener("click", (event) => {
    const deleteButton = event.target.closest('[data-action="delete-grade"]');
    if (!deleteButton) {
      return;
    }

    deleteButton.closest("tr")?.remove();
    if (!elements.gradeConfigBody.children.length) {
      addGradeRow();
    }
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    elements.dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.dropZone.classList.add("is-dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    elements.dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.dropZone.classList.remove("is-dragover");
    });
  });

  elements.dropZone.addEventListener("drop", (event) => {
    const [file] = event.dataTransfer.files;
    if (file) {
      applySelectedFile(file);
    }
  });
}

function toggleNavigation() {
  const isCollapsed = document.body.classList.toggle("nav-collapsed");
  elements.navToggleButton.setAttribute("aria-expanded", String(!isCollapsed));
  elements.navToggleButton.setAttribute(
    "aria-label",
    isCollapsed ? "Expand navigation" : "Collapse navigation",
  );
}

async function loadDashboard(preferredBatchId = state.activeBatchId) {
  try {
    const payload = await apiRequest("/api/dashboard");
    state.gradeConfig = payload.gradeConfig;
    state.batches = payload.batches;
    renderGradeConfig();
    renderBatchList();

    const nextBatchId =
      preferredBatchId &&
      state.batches.some((batch) => batch.id === preferredBatchId)
        ? preferredBatchId
        : (state.batches[0]?.id ?? null);

    if (nextBatchId) {
      await loadBatch(nextBatchId);
      return;
    }

    state.activeBatchId = null;
    state.activeBatch = null;
    state.departmentFilter = "All Departments";
    renderActiveBatch();
    syncExportButtons();
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function loadBatch(batchId) {
  try {
    const payload = await apiRequest(`/api/batches/${batchId}`);
    state.activeBatchId = batchId;
    state.activeBatch = payload.analytics;
    state.gradeConfig = payload.gradeConfig;
    state.departmentFilter = state.activeBatch.departments.includes(
      state.departmentFilter,
    )
      ? state.departmentFilter
      : "All Departments";

    renderGradeConfig();
    renderBatchList();
    renderDepartmentOptions();
    renderActiveBatch();
    syncExportButtons();
  } catch (error) {
    showToast(error.message, "error");
  }
}

function handleFileSelection(event) {
  const [file] = event.target.files;
  if (file) {
    applySelectedFile(file);
  }
}

function applySelectedFile(file) {
  state.selectedFile = file;
  elements.selectedFileLabel.textContent = `${file.name} (${formatFileSize(file.size)})`;
}

async function handleUpload() {
  if (!state.selectedFile) {
    showToast("Choose a PDF file before uploading.", "error");
    return;
  }

  setBusy(elements.uploadButton, true, "Uploading...");
  try {
    const fileData = await readFileAsBase64(state.selectedFile);
    const payload = await apiRequest("/api/batches", {
      method: "POST",
      body: {
        fileName: state.selectedFile.name,
        fileData,
        batchName: elements.batchNameInput.value.trim(),
      },
    });

    showToast("Result batch uploaded successfully.", "success");
    state.selectedFile = null;
    elements.pdfFileInput.value = "";
    elements.batchNameInput.value = "";
    elements.selectedFileLabel.textContent = "No file selected";

    await loadDashboard(payload.analytics.batch.id);
    activateTab("results");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    setBusy(elements.uploadButton, false, "Upload and Analyse");
  }
}

function activateTab(tabName) {
  const hasTab = elements.tabPanels.some(
    (panel) => panel.dataset.tabPanel === tabName,
  );
  if (!hasTab) {
    return;
  }

  state.activeTab = tabName;
  elements.tabButtons.forEach((button) => {
    const isActive = button.dataset.tabTarget === tabName;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });
  elements.tabPanels.forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.tabPanel === tabName);
  });
}

function activateResultTab(tabName) {
  const hasTab = elements.resultPanels.some(
    (panel) => panel.dataset.resultPanel === tabName,
  );
  if (!hasTab) {
    return;
  }

  state.activeResultTab = tabName;
  elements.resultTabButtons.forEach((button) => {
    const isActive = button.dataset.resultTabTarget === tabName;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });
  elements.resultPanels.forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.resultPanel === tabName);
  });
}

function renderGradeConfig() {
  if (!state.gradeConfig.length) {
    addGradeRow();
    return;
  }

  elements.gradeConfigBody.innerHTML = state.gradeConfig
    .map(
      (row) => `
                <tr>
                    <td><input class="text-input" data-field="grade" type="text" value="${escapeHtml(row.grade)}"></td>
                    <td><input class="text-input" data-field="points" type="number" step="0.01" min="0" value="${row.points}"></td>
                    <td><input data-field="isPass" type="checkbox" ${row.is_pass ? "checked" : ""}></td>
                    <td class="grade-row-actions">
                        <button class="delete-button" data-action="delete-grade" type="button">Remove</button>
                    </td>
                </tr>
            `,
    )
    .join("");
}

function addGradeRow() {
  const row = document.createElement("tr");
  row.innerHTML = `
        <td><input class="text-input" data-field="grade" type="text" value=""></td>
        <td><input class="text-input" data-field="points" type="number" step="0.01" min="0" value="0"></td>
        <td><input data-field="isPass" type="checkbox"></td>
        <td class="grade-row-actions">
            <button class="delete-button" data-action="delete-grade" type="button">Remove</button>
        </td>
    `;
  elements.gradeConfigBody.appendChild(row);
}

async function saveGradeConfig() {
  const grades = Array.from(
    elements.gradeConfigBody.querySelectorAll("tr"),
  ).map((row) => ({
    grade: row.querySelector('[data-field="grade"]').value.trim(),
    points: Number(row.querySelector('[data-field="points"]').value),
    is_pass: row.querySelector('[data-field="isPass"]').checked,
  }));

  if (grades.some((row) => !row.grade)) {
    showToast("Every grade row needs a grade label.", "error");
    return;
  }

  setBusy(elements.saveConfigButton, true, "Saving...");
  try {
    const payload = await apiRequest("/api/grade-config", {
      method: "PUT",
      body: { grades },
    });

    state.gradeConfig = payload.gradeConfig;
    renderGradeConfig();
    showToast("Grade scale updated.", "success");

    if (state.activeBatchId) {
      await loadBatch(state.activeBatchId);
    }
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    setBusy(elements.saveConfigButton, false, "Save Scale");
  }
}

function renderBatchList() {
  if (!state.batches.length) {
    elements.batchList.innerHTML =
      '<div class="empty-state">No result batches have been uploaded yet.</div>';
    return;
  }

  elements.batchList.innerHTML = state.batches
    .map((batch) => {
      const isActive = batch.id === state.activeBatchId ? "is-active" : "";
      return `
                <article class="batch-card ${isActive}">
                    <h4>${escapeHtml(batch.name)}</h4>
                    <p class="batch-meta">
                        ${escapeHtml(batch.exam_name)}<br>
                        ${escapeHtml(batch.institution || "Institution not detected")}<br>
                        ${batch.total_students} students, ${batch.total_courses} subjects
                    </p>
                    <div class="batch-card-actions">
                        <button class="secondary-button" data-action="select-batch" data-batch-id="${batch.id}" type="button">Open</button>
                        <button class="delete-button" data-action="delete-batch" data-batch-id="${batch.id}" type="button">Delete</button>
                    </div>
                </article>
            `;
    })
    .join("");
}

function renderDepartmentOptions() {
  const departments = state.activeBatch?.departments ?? [];
  const options = ["All Departments", ...departments]
    .map(
      (department) =>
        `<option value="${escapeHtml(department)}" ${
          department === state.departmentFilter ? "selected" : ""
        }>${escapeHtml(department)}</option>`,
    )
    .join("");
  elements.departmentFilter.innerHTML = options;
}

function renderActiveBatch() {
  if (!state.activeBatch) {
    elements.activeBatchMeta.innerHTML =
      '<p class="empty-copy">Upload a result PDF to populate the analytics dashboard.</p>';
    elements.summaryCards.innerHTML = "";
    elements.topStudentsTable.innerHTML =
      '<div class="empty-state">No ranking data available.</div>';
    elements.subjectsBody.innerHTML =
      '<tr><td colspan="9"><div class="empty-state">No subject data available.</div></td></tr>';
    elements.studentsBody.innerHTML =
      '<tr><td colspan="7"><div class="empty-state">No student data available.</div></td></tr>';
    elements.unknownGradeNotice.classList.add("hidden");
    syncExportButtons();
    return;
  }

  renderBatchMeta();
  renderUnknownNotice();
  renderSummaryCards();
  renderRankingTables();
  renderSubjectsTable();
  renderStudentsTable();
  syncExportButtons();
}

function renderBatchMeta() {
  const batch = state.activeBatch.batch;
  const visibleStudents = getVisibleStudents();
  const visibleSubjects = getVisibleSubjects();
  const filterText =
    state.departmentFilter === "All Departments"
      ? "Showing all departments"
      : `Showing ${state.departmentFilter}`;

  elements.activeBatchMeta.innerHTML = `
        <p class="eyebrow">Active Batch</p>
        <h2>${escapeHtml(batch.name)}</h2>
        <p>${escapeHtml(batch.exam_name)}</p>
        <p>${escapeHtml(batch.institution || "Institution not detected")}</p>
        <p>${filterText}. ${visibleStudents.length} students and ${visibleSubjects.length} subject rows in the current view.</p>
        <p>Uploaded on ${formatDate(batch.uploaded_at)} from ${escapeHtml(batch.source_filename)}</p>
    `;
}

function renderUnknownNotice() {
  const unknownGrades = state.activeBatch.summary.unknown_grades ?? [];
  if (!unknownGrades.length) {
    elements.unknownGradeNotice.classList.add("hidden");
    elements.unknownGradeNotice.textContent = "";
    return;
  }

  elements.unknownGradeNotice.classList.remove("hidden");
  elements.unknownGradeNotice.textContent =
    `Grades without a configured point mapping were detected: ${unknownGrades.join(", ")}. ` +
    "They are currently treated as zero points and not passed.";
}

function renderSummaryCards() {
  const summary = buildVisibleSummary();
  const cards = [
    { label: "Students", value: summary.totalStudents },
    { label: "Subjects", value: summary.totalCourses },
    { label: "Average GPA", value: summary.averageGpa.toFixed(2) },
    { label: "Highest GPA", value: summary.highestGpa.toFixed(2) },
    { label: "Lowest GPA", value: summary.lowestGpa.toFixed(2) },
  ];

  elements.summaryCards.innerHTML = cards
    .map(
      (card) => `
                <article class="summary-card">
                    <p class="summary-card-label">${escapeHtml(card.label)}</p>
                    <p class="summary-card-value">${escapeHtml(String(card.value))}</p>
                </article>
            `,
    )
    .join("");
}

function renderRankingTables() {
  const visibleStudents = [...getVisibleStudents()].sort(
    (left, right) =>
      right.gpa - left.gpa || left.register_no.localeCompare(right.register_no),
  );
  const topStudents = visibleStudents.slice(0, 10);

  elements.topStudentsTable.innerHTML = buildRankingTable(
    topStudents,
    "No student records available.",
  );
}

function buildRankingTable(students, emptyMessage) {
  if (!students.length) {
    return `<div class="empty-state">${escapeHtml(emptyMessage)}</div>`;
  }

  return `
        <div class="table-wrap">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Register No</th>
                        <th>Department</th>
                        <th>GPA</th>
                    </tr>
                </thead>
                <tbody>
                    ${students
                      .map(
                        (student) => `
                                <tr>
                                    <td>${escapeHtml(student.register_no)}</td>
                                    <td>${escapeHtml(student.department_name)}</td>
                                    <td>${student.gpa.toFixed(2)}</td>
                                </tr>
                            `,
                      )
                      .join("")}
                </tbody>
            </table>
        </div>
    `;
}

function renderSubjectsTable() {
  const subjects = getVisibleSubjects();
  if (!subjects.length) {
    elements.subjectsBody.innerHTML =
      '<tr><td colspan="9"><div class="empty-state">No subject rows available for this filter.</div></td></tr>';
    return;
  }

  elements.subjectsBody.innerHTML = subjects
    .map(
      (subject) => `
                <tr>
                    <td>${escapeHtml(subject.department_name)}</td>
                    <td>${escapeHtml(subject.course_code)}</td>
                    <td>${escapeHtml(subject.course_name)}</td>
                    <td>
                        <input
                            class="credit-input"
                            data-course-code="${escapeHtml(subject.course_code)}"
                            data-department-name="${escapeHtml(subject.department_name)}"
                            type="number"
                            min="0.1"
                            step="0.5"
                            value="${subject.credits}"
                        >
                    </td>
                    <td>${subject.appeared_count}</td>
                    <td>${subject.passed_count}</td>
                    <td>${subject.failed_count}</td>
                    <td>${subject.absent_count}</td>
                    <td>${subject.pass_percentage.toFixed(2)}</td>
                </tr>
            `,
    )
    .join("");
}

function renderStudentsTable() {
  const searchTerm = elements.studentSearchInput.value.trim().toUpperCase();
  const students = getVisibleStudents().filter(
    (student) =>
      !searchTerm || student.register_no.toUpperCase().includes(searchTerm),
  );

  if (!students.length) {
    elements.studentsBody.innerHTML =
      '<tr><td colspan="7"><div class="empty-state">No students match the current filter.</div></td></tr>';
    return;
  }

  elements.studentsBody.innerHTML = students
    .map((student) => {
      const gradeMarkup = student.grades
        .map((grade) => {
          const chipClasses = [
            "grade-chip",
            grade.grade === "Absent" ? "is-absent" : "",
            grade.points === 0 && grade.grade !== "Absent" ? "is-fail" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return `<span class="${chipClasses}">${escapeHtml(
            `${grade.course_code}: ${grade.grade}`,
          )}</span>`;
        })
        .join("");

      return `
                <tr>
                    <td>${escapeHtml(student.register_no)}</td>
                    <td>${escapeHtml(student.department_name)}</td>
                    <td>${student.gpa.toFixed(2)}</td>
                    <td>${student.passed_count}</td>
                    <td>${student.failed_count}</td>
                    <td>${student.subject_count}</td>
                    <td><div class="grade-chip-list">${gradeMarkup}</div></td>
                </tr>
            `;
    })
    .join("");
}

async function saveCourseCredits() {
  if (!state.activeBatchId) {
    showToast("Upload or open a batch before saving credits.", "error");
    return;
  }

  const inputs = Array.from(
    elements.subjectsBody.querySelectorAll(".credit-input"),
  );
  if (!inputs.length) {
    showToast("No subject rows are available to update.", "error");
    return;
  }

  const courses = inputs.map((input) => ({
    department_name: input.dataset.departmentName,
    course_code: input.dataset.courseCode,
    credits: Number(input.value),
  }));

  setBusy(elements.saveCreditsButton, true, "Saving...");
  try {
    await apiRequest(`/api/batches/${state.activeBatchId}/courses`, {
      method: "PUT",
      body: { courses },
    });
    showToast("Course credits updated.", "success");
    await loadBatch(state.activeBatchId);
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    setBusy(elements.saveCreditsButton, false, "Save Credits");
  }
}

async function downloadWordReport() {
  if (!state.activeBatchId) {
    showToast("Open a batch before downloading a report.", "error");
    return;
  }

  const threshold = Number(elements.gpaThresholdInput.value);
  if (Number.isNaN(threshold) || threshold < 0 || threshold > 10) {
    showToast("Enter a GPA threshold between 0 and 10.", "error");
    return;
  }

  const button = elements.downloadWordButton;
  const originalLabel = button.textContent;
  setBusy(button, true, "Preparing Word...");

  try {
    const response = await fetch(
      `/api/batches/${state.activeBatchId}/exports/word?threshold=${encodeURIComponent(threshold)}`,
      { headers: { Accept: "*/*" } },
    );

    if (!response.ok) {
      let message = "Unable to generate the report.";
      const contentType = response.headers.get("Content-Type") || "";
      if (contentType.includes("application/json")) {
        const payload = await response.json();
        message = payload.error || message;
      } else {
        const text = await response.text();
        message = text.trim() || message;
      }
      throw new Error(message);
    }

    const blob = await response.blob();
    if (!blob.size) {
      throw new Error("The server returned an empty report.");
    }

    const downloadUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = downloadUrl;
    anchor.download = getFileNameFromDisposition(
      response.headers.get("Content-Disposition"),
    );
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(downloadUrl);
    showToast("Word analysis downloaded.", "success");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    setBusy(button, false, originalLabel);
  }
}

async function downloadRegisterExcel() {
  if (!state.activeBatchId) {
    showToast("Open a batch before downloading the GPA register.", "error");
    return;
  }

  const params = new URLSearchParams();
  if (state.departmentFilter !== "All Departments") {
    params.set("department", state.departmentFilter);
  }
  const searchTerm = elements.studentSearchInput.value.trim();
  if (searchTerm) {
    params.set("search", searchTerm);
  }

  const button = elements.downloadRegisterExcelButton;
  const originalLabel = button.textContent;
  setBusy(button, true, "Preparing Excel...");

  try {
    const query = params.toString();
    const response = await fetch(
      `/api/batches/${state.activeBatchId}/exports/register-excel${query ? `?${query}` : ""}`,
      { headers: { Accept: "*/*" } },
    );
    if (!response.ok) {
      let message = "Unable to generate the GPA register.";
      const contentType = response.headers.get("Content-Type") || "";
      if (contentType.includes("application/json")) {
        const payload = await response.json();
        message = payload.error || message;
      } else {
        const text = await response.text();
        message = text.trim() || message;
      }
      throw new Error(message);
    }

    const blob = await response.blob();
    if (!blob.size) {
      throw new Error("The server returned an empty register.");
    }

    const downloadUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = downloadUrl;
    anchor.download = getFileNameFromDisposition(
      response.headers.get("Content-Disposition"),
    );
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(downloadUrl);
    showToast("GPA register downloaded.", "success");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    setBusy(button, false, originalLabel);
  }
}

function getVisibleStudents() {
  const students = state.activeBatch?.students ?? [];
  if (state.departmentFilter === "All Departments") {
    return students;
  }
  return students.filter(
    (student) => student.department_name === state.departmentFilter,
  );
}

function getVisibleSubjects() {
  const subjects = state.activeBatch?.subjects ?? [];
  if (state.departmentFilter === "All Departments") {
    return subjects;
  }
  return subjects.filter(
    (subject) => subject.department_name === state.departmentFilter,
  );
}

function buildVisibleSummary() {
  const students = getVisibleStudents();
  const subjects = getVisibleSubjects();
  if (!students.length) {
    return {
      totalStudents: 0,
      totalCourses: subjects.length,
      averageGpa: 0,
      highestGpa: 0,
      lowestGpa: 0,
    };
  }

  const gpas = students.map((student) => student.gpa);
  return {
    totalStudents: students.length,
    totalCourses: subjects.length,
    averageGpa: gpas.reduce((total, value) => total + value, 0) / gpas.length,
    highestGpa: Math.max(...gpas),
    lowestGpa: Math.min(...gpas),
  };
}

async function apiRequest(url, options = {}) {
  const requestOptions = {
    ...options,
    headers: { Accept: "application/json" },
  };
  if (options.body !== undefined) {
    requestOptions.body = JSON.stringify(options.body);
    requestOptions.headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url, requestOptions);
  if (response.status === 204) {
    return null;
  }

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request failed.");
  }

  return payload;
}

function setBusy(button, busy, label) {
  button.disabled = busy;
  button.textContent = label;
}

function syncExportButtons() {
  const disabled = !state.activeBatch;
  elements.downloadWordButton.disabled = disabled;
  elements.downloadRegisterExcelButton.disabled = disabled;
}

function showToast(message, type = "info") {
  elements.statusToast.textContent = message;
  elements.statusToast.className = `status-toast ${type}`;
  if (toastTimer) {
    clearTimeout(toastTimer);
  }
  toastTimer = window.setTimeout(() => {
    elements.statusToast.className = "status-toast hidden";
  }, 3400);
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result);
      resolve(result.split(",", 2)[1]);
    };
    reader.onerror = () =>
      reject(new Error("Unable to read the selected file."));
    reader.readAsDataURL(file);
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatFileSize(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileNameFromDisposition(disposition) {
  if (!disposition) {
    return "analysis-download";
  }

  const encodedMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encodedMatch) {
    return decodeURIComponent(encodedMatch[1]);
  }

  const match = disposition.match(/filename="([^"]+)"/i);
  return match ? match[1] : "analysis-download";
}

// Handle header collapse on scroll
const header = document.querySelector(".site-header");

function handleCollapseByScroll(scrollTop) {
  if (!header) return;
  if (scrollTop > 50) {
    header.classList.add("is-collapsed");
  } else {
    header.classList.remove("is-collapsed");
  }
}

// Window/document scrolling
window.addEventListener(
  "scroll",
  () => {
    const currentScroll = window.scrollY || document.documentElement.scrollTop;
    handleCollapseByScroll(currentScroll);
  },
  { passive: true },
);

// Panels that may scroll independently (e.g. result panel shell)
const scrollablePanels = Array.from(
  document.querySelectorAll(".result-panel-shell, .table-wrap, .tab-panels"),
);
scrollablePanels.forEach((el) => {
  el.addEventListener(
    "scroll",
    (ev) => {
      handleCollapseByScroll(ev.target.scrollTop || ev.target.scrollY || 0);
    },
    { passive: true },
  );
});
