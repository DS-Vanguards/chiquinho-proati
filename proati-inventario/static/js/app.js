const TABS = {
  tablets: { label: "Tablets", kind: "inventory", skipStatus: true, fixedModel: true },
  regular: { label: "Regular", kind: "inventory" },
  tecnico: { label: "Técnico", kind: "inventory" },
  manutencao: { label: "Manutenção", kind: "maintenance" },
  manutencao_tecnico: { label: "Manutenção Técnico", kind: "maintenance" },
};

const state = {
  tab: "tablets",
  items: [],
};

function $(id) {
  return document.getElementById(id);
}

function showToast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2800);
}

async function request(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.erro || "Falha na requisição");
  return data;
}

function currentMeta() {
  return TABS[state.tab];
}

function isMaintenance() {
  return currentMeta().kind === "maintenance";
}

function badgeClass(status) {
  const map = {
    "Perfeito estado": "badge-t",
    "Danos periféricos": "badge-yellow",
    "Danos físicos": "badge-n",
    "Aguardando chamado": "badge-yellow",
    "Chamado realizado": "badge-t",
    "Aguardando inspeção": "badge-n",
  };
  return map[status] || "badge-t";
}

function renderStats(items) {
  const grid = $("summary-grid");
  if (state.tab === "tablets") {
    grid.innerHTML = `
      <div class="stat-item"><div class="stat-label">Tablets</div><div class="stat-val blue">${items.length}</div><div class="stat-unit">unidades</div></div>
      <div class="stat-item"><div class="stat-label">Modelo</div><div class="stat-val" style="font-size:15px;color:var(--pastel-purple)">${window.PROATI.tabletModel}</div><div class="stat-unit">único da escola</div></div>
      <div class="stat-item"><div class="stat-label">Aba</div><div class="stat-val green">TABLETS</div><div class="stat-unit">inventário</div></div>`;
    return;
  }
  if (isMaintenance()) {
    const a = items.filter((i) => i.status === "Aguardando chamado").length;
    const b = items.filter((i) => i.status === "Chamado realizado").length;
    const c = items.filter((i) => i.status === "Aguardando inspeção").length;
    grid.innerHTML = `
      <div class="stat-item"><div class="stat-label">Total</div><div class="stat-val yellow">${items.length}</div><div class="stat-unit">equipamentos</div></div>
      <div class="stat-item"><div class="stat-label">Aguardando chamado</div><div class="stat-val blue">${a}</div><div class="stat-unit">itens</div></div>
      <div class="stat-item"><div class="stat-label">Chamado realizado</div><div class="stat-val green">${b}</div><div class="stat-unit">itens</div></div>
      <div class="stat-item"><div class="stat-label">Aguardando inspeção</div><div class="stat-val" style="color:var(--pastel-orange)">${c}</div><div class="stat-unit">itens</div></div>`;
    return;
  }
  const ok = items.filter((i) => i.status === "Perfeito estado").length;
  const peri = items.filter((i) => i.status === "Danos periféricos").length;
  const fis = items.filter((i) => i.status === "Danos físicos").length;
  grid.innerHTML = `
    <div class="stat-item"><div class="stat-label">Total</div><div class="stat-val yellow">${items.length}</div><div class="stat-unit">unidades</div></div>
    <div class="stat-item"><div class="stat-label">Perfeito estado</div><div class="stat-val green">${ok}</div><div class="stat-unit">unidades</div></div>
    <div class="stat-item"><div class="stat-label">Danos periféricos</div><div class="stat-val blue">${peri}</div><div class="stat-unit">unidades</div></div>
    <div class="stat-item"><div class="stat-label">Danos físicos</div><div class="stat-val" style="color:var(--pastel-pink)">${fis}</div><div class="stat-unit">unidades</div></div>`;
}

function renderHead() {
  const maintenance = isMaintenance();
  const skipStatus = currentMeta().skipStatus;
  $("equip-head").innerHTML = `<tr>
    <th class="th-n">#</th>
    <th class="th-tab">Modelo equipamento</th>
    <th>Serial equipamento</th>
    <th>Numeração</th>
    ${maintenance ? `<th class="th-note">Descrição do problema</th>` : ""}
    ${skipStatus ? "" : `<th style="text-align:center">Status</th>`}
    ${window.PROATI.canEdit ? `<th style="width:140px">Ações</th>` : ""}
  </tr>`;
}

function renderRows(items) {
  const body = $("equip-body");
  const maintenance = isMaintenance();
  const skipStatus = currentMeta().skipStatus;
  if (!items.length) {
    const cols = 4 + (maintenance ? 1 : 0) + (skipStatus ? 0 : 1) + (window.PROATI.canEdit ? 1 : 0);
    body.innerHTML = `<tr><td colspan="${cols}" class="empty">Nenhum equipamento registrado.</td></tr>`;
    return;
  }
  body.innerHTML = items
    .map((item, idx) => {
      const actions = window.PROATI.canEdit
        ? `<td class="actions-cell">
            <button class="btn-sm" data-edit="${item.id}" type="button">Editar</button>
            <button class="btn-sm btn-danger" data-del="${item.id}" type="button">Remover</button>
          </td>`
        : "";
      return `<tr>
        <td class="td-num"><span class="num-badge">${idx + 1}</span></td>
        <td class="td-tab">${escapeHtml(item.modelo)}</td>
        <td class="td-time">${escapeHtml(item.serial)}</td>
        <td>${escapeHtml(item.numeracao)}</td>
        ${maintenance ? `<td class="td-note">${escapeHtml(item.problema)}</td>` : ""}
        ${skipStatus ? "" : `<td style="text-align:center"><span class="badge ${badgeClass(item.status)}">${escapeHtml(item.status)}</span></td>`}
        ${actions}
      </tr>`;
    })
    .join("");
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function loadEquipment() {
  const data = await request(`/api/equipamentos?tab=${encodeURIComponent(state.tab)}`);
  state.items = data.itens || [];
  renderStats(state.items);
  renderHead();
  renderRows(state.items);
}

function openModal(item) {
  const meta = currentMeta();
  $("modal-title").textContent = item ? "Alterar equipamento" : "Novo equipamento";
  $("equip-id").value = item ? item.id : "";
  $("f-modelo").value = meta.fixedModel ? window.PROATI.tabletModel : item?.modelo || "";
  $("f-modelo").readOnly = !!meta.fixedModel;
  $("f-modelo").required = !meta.fixedModel;
  $("f-modelo").classList.toggle("fixed", !!meta.fixedModel);
  $("f-serial").value = item?.serial || "";
  $("f-numeracao").value = item?.numeracao || "";
  $("f-problema").value = item?.problema || "";
  $("wrap-problema").style.display = meta.kind === "maintenance" ? "block" : "none";
  $("wrap-status").style.display = meta.skipStatus ? "none" : "block";
  const select = $("f-status");
  const options = meta.kind === "maintenance" ? window.PROATI.maintenanceStatuses : window.PROATI.inventoryStatuses;
  select.innerHTML = options.map((s) => `<option value="${s}">${s}</option>`).join("");
  if (item?.status) select.value = item.status;
  $("equip-modal").classList.add("open");
}

function closeModal() {
  $("equip-modal").classList.remove("open");
}

async function saveEquipment(event) {
  event.preventDefault();
  const meta = currentMeta();
  const id = $("equip-id").value;
  const payload = {
    tab: state.tab,
    modelo: $("f-modelo").value.trim(),
    serial: $("f-serial").value.trim(),
    numeracao: $("f-numeracao").value.trim(),
    problema: $("f-problema").value.trim(),
    status: $("f-status").value,
  };
  if (meta.fixedModel) payload.modelo = window.PROATI.tabletModel;
  try {
    if (id) {
      await request(`/api/equipamentos/${id}`, { method: "PUT", body: JSON.stringify(payload) });
      showToast("✔ Equipamento atualizado");
    } else {
      await request("/api/equipamentos", { method: "POST", body: JSON.stringify(payload) });
      showToast("✔ Equipamento adicionado");
    }
    closeModal();
    await loadEquipment();
  } catch (err) {
    showToast("✘ " + err.message);
  }
}

async function removeEquipment(id) {
  if (!confirm("Remover este equipamento?")) return;
  try {
    await request(`/api/equipamentos/${id}`, { method: "DELETE" });
    showToast("✔ Removido");
    await loadEquipment();
  } catch (err) {
    showToast("✘ " + err.message);
  }
}

function roleLabel(role) {
  const map = {
    admin: "Admin",
    proati: "Proati",
    coordenador: "Coordenador",
    visualizador: "Visualizador",
  };
  return map[role] || role;
}

async function loadUsers() {
  if (!window.PROATI.isAdmin) return;
  const data = await request("/api/usuarios");
  const body = $("users-body");
  if (!data.usuarios.length) {
    body.innerHTML = `<tr><td colspan="4" class="empty">Nenhum usuário.</td></tr>`;
    return;
  }
  body.innerHTML = data.usuarios
    .map((user) => {
      const options = window.PROATI.roles
        .map((r) => `<option value="${r}" ${r === user.role ? "selected" : ""}>${roleLabel(r)}</option>`)
        .join("");
      const pending = user.must_reset_password
        ? `<span class="badge badge-yellow">Aguardando senha</span>`
        : "";
      const cargo = user.is_self
        ? `<span class="badge badge-${user.role}">${roleLabel(user.role)}</span><span class="text-muted">Sua conta</span>`
        : `<select class="form-input inline-select" data-role="${user.id}">${options}</select>
           <button class="btn-sm btn-save-role" data-save-role="${user.id}" type="button">Salvar</button>`;
      const delBtn = user.is_self
        ? ""
        : `<button class="btn-sm btn-danger" data-del-user="${user.id}" type="button">Excluir conta</button>`;
      return `<tr>
        <td><strong>${escapeHtml(user.username)}</strong> ${pending}</td>
        <td>${escapeHtml(user.email)}</td>
        <td><div class="cargo-cell">${cargo}</div></td>
        <td>
          <div class="actions-stack">
            <button class="btn-sm btn-warning" data-reset="${user.id}" type="button">Redefinir senha</button>
            ${delBtn}
          </div>
        </td>
      </tr>`;
    })
    .join("");
}

async function saveRole(userId) {
  const select = document.querySelector(`[data-role="${userId}"]`);
  try {
    await request(`/api/usuarios/${userId}/cargo`, {
      method: "POST",
      body: JSON.stringify({ role: select.value }),
    });
    showToast("✔ Cargo atualizado");
    await loadUsers();
  } catch (err) {
    showToast("✘ " + err.message);
  }
}

async function resetPassword(userId) {
  if (!confirm("Redefinir a senha deste usuário? Ele poderá entrar só com o usuário/e-mail e criar uma senha nova.")) return;
  try {
    await request(`/api/usuarios/${userId}/redefinir-senha`, { method: "POST" });
    showToast("✔ Senha redefinida. O usuário entra sem senha e cria uma nova.");
    await loadUsers();
  } catch (err) {
    showToast("✘ " + err.message);
  }
}

async function deleteUser(userId) {
  if (!confirm("Excluir esta conta permanentemente?")) return;
  try {
    await request(`/api/usuarios/${userId}`, { method: "DELETE" });
    showToast("✔ Conta excluída");
    await loadUsers();
  } catch (err) {
    showToast("✘ " + err.message);
  }
}

async function loadBlocks() {
  if (!window.PROATI.isAdmin) return;
  const body = $("blocks-body");
  if (!body) return;
  const data = await request("/api/bloqueios");
  const rows = data.bloqueios || [];
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="5" class="empty">Nenhuma máquina bloqueada.</td></tr>`;
    return;
  }
  body.innerHTML = rows
    .map(
      (row) => `<tr>
        <td style="font-family:var(--mono);font-size:11px">${escapeHtml(row.token)}</td>
        <td>${escapeHtml(row.ip)}</td>
        <td><span class="badge ${row.strike_level >= 2 ? "badge-n" : "badge-yellow"}">${escapeHtml(row.level_label)}</span></td>
        <td>${escapeHtml(row.blocked_until)}</td>
        <td>
          <div class="actions-stack">
            <button class="btn-sm btn-warning" data-reduce="${row.id}" type="button">Alterar bloqueio</button>
            <button class="btn-sm btn-danger" data-unblock="${row.id}" type="button">Remover bloqueio</button>
          </div>
        </td>
      </tr>`
    )
    .join("");
}

function openBlockModal(id) {
  $("block-id").value = id;
  $("block-amount").value = "1";
  $("block-unit").value = "dias";
  $("block-modal").classList.add("open");
}

function closeBlockModal() {
  const modal = $("block-modal");
  if (modal) modal.classList.remove("open");
}

async function saveBlockDuration(event) {
  event.preventDefault();
  const id = $("block-id").value;
  const amount = $("block-amount").value;
  const unit = $("block-unit").value;
  try {
    await request(`/api/bloqueios/${id}/tempo`, {
      method: "POST",
      body: JSON.stringify({ amount, unit }),
    });
    showToast("✔ Tempo de bloqueio atualizado");
    closeBlockModal();
    await loadBlocks();
  } catch (err) {
    showToast("✘ " + err.message);
  }
}

async function removeBlock(id) {
  if (!confirm("Remover o bloqueio desta máquina?")) return;
  try {
    await request(`/api/bloqueios/${id}`, { method: "DELETE" });
    showToast("✔ Bloqueio removido");
    await loadBlocks();
  } catch (err) {
    showToast("✘ " + err.message);
  }
}

function showView(tab) {
  state.tab = tab;
  document.querySelectorAll(".nav-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  const isAdminTab = tab === "admin";
  $("view-inventory").classList.toggle("active", !isAdminTab);
  const adminView = $("view-admin");
  if (adminView) adminView.classList.toggle("active", isAdminTab);
  if (isAdminTab) {
    Promise.all([loadUsers(), loadBlocks()]).catch((err) => showToast("✘ " + err.message));
    return;
  }
  $("tab-label").textContent = currentMeta().label.toUpperCase();
  loadEquipment().catch((err) => showToast("✘ " + err.message));
}

document.querySelectorAll(".nav-tab").forEach((btn) => {
  btn.addEventListener("click", () => showView(btn.dataset.tab));
});

const addBtn = $("btn-add");
if (addBtn) addBtn.addEventListener("click", () => openModal(null));
$("modal-close").addEventListener("click", closeModal);
$("modal-cancel").addEventListener("click", closeModal);
$("equip-modal").addEventListener("click", (e) => {
  if (e.target.id === "equip-modal") closeModal();
});
$("equip-form").addEventListener("submit", saveEquipment);
$("equip-body").addEventListener("click", (e) => {
  const editId = e.target.dataset.edit;
  const delId = e.target.dataset.del;
  if (editId) {
    const item = state.items.find((i) => String(i.id) === String(editId));
    if (item) openModal(item);
  }
  if (delId) removeEquipment(delId);
});

const usersBody = $("users-body");
if (usersBody) {
  usersBody.addEventListener("click", (e) => {
    const saveBtn = e.target.closest("[data-save-role]");
    const delBtn = e.target.closest("[data-del-user]");
    const resetBtn = e.target.closest("[data-reset]");
    if (saveBtn) saveRole(saveBtn.dataset.saveRole);
    if (delBtn) deleteUser(delBtn.dataset.delUser);
    if (resetBtn) resetPassword(resetBtn.dataset.reset);
  });
}

const blocksBody = $("blocks-body");
if (blocksBody) {
  blocksBody.addEventListener("click", (e) => {
    const reduceBtn = e.target.closest("[data-reduce]");
    const unblockBtn = e.target.closest("[data-unblock]");
    if (reduceBtn) openBlockModal(reduceBtn.dataset.reduce);
    if (unblockBtn) removeBlock(unblockBtn.dataset.unblock);
  });
}

const blockForm = $("block-form");
if (blockForm) {
  blockForm.addEventListener("submit", saveBlockDuration);
  $("block-modal-close").addEventListener("click", closeBlockModal);
  $("block-modal-cancel").addEventListener("click", closeBlockModal);
  $("block-modal").addEventListener("click", (e) => {
    if (e.target.id === "block-modal") closeBlockModal();
  });
}

showView("tablets");
