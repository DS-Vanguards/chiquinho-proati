const TABS = {
  tablets: { label: "Tablets", kind: "inventory", skipStatus: true, fixedModel: true },
  regular: { label: "Regular", kind: "inventory" },
  tecnico: { label: "Técnico", kind: "inventory" },
  manutencao: { label: "Manutenção", kind: "maintenance" },
  manutencao_tecnico: { label: "Manutenção Técnico", kind: "maintenance" },
  gestao: { label: "Gestão", kind: "gestao" },
  gestao_tablet: { label: "Gestão Tablet", kind: "gestao" },
  gestao_tecnico: { label: "Gestão Técnico", kind: "gestao" },
};

const state = {
  tab: "tablets",
  items: [],
  users: [],
  assignableRoles: [],
  roleUserId: "",
  pickedRole: "",
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

function csrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";
}

async function request(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const token = csrfToken();
  if (token) {
    if (!headers.has("X-CSRFToken")) headers.set("X-CSRFToken", token);
    if (!headers.has("X-CSRF-Token")) headers.set("X-CSRF-Token", token);
  }
  let body = options.body;
  if (token && typeof body === "string") {
    try {
      const parsed = JSON.parse(body);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed) && !parsed.csrf_token) {
        parsed.csrf_token = token;
        body = JSON.stringify(parsed);
      }
    } catch (err) {
      /* keep original body */
    }
  }
  const res = await fetch(url, { credentials: "same-origin", ...options, headers, body });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.erro || "Falha na requisição");
  return data;
}

function currentMeta() {
  return TABS[state.tab] || TABS.tablets;
}

function isMaintenance() {
  return currentMeta().kind === "maintenance";
}

function isGestao() {
  return currentMeta().kind === "gestao";
}

function badgeClass(status) {
  const map = {
    "Perfeito estado": "badge-t",
    "Danos periféricos": "badge-yellow",
    "Aguardando chamado": "badge-yellow",
    "Chamado realizado": "badge-t",
    "Aguardando inspeção": "badge-n",
    "Em uso": "badge-t",
    Pendente: "badge-yellow",
    Entregues: "badge-ok",
  };
  return map[status] || "badge-t";
}

function renderStats(items) {
  const grid = $("summary-grid");
  if (isGestao()) {
    const uso = items.filter((i) => i.status === "Em uso").length;
    const pend = items.filter((i) => i.status === "Pendente").length;
    const ok = items.filter((i) => i.status === "Entregues").length;
    grid.innerHTML = `
      <div class="stat-item"><div class="stat-label">Total</div><div class="stat-val yellow">${items.length}</div><div class="stat-unit">relatórios</div></div>
      <div class="stat-item"><div class="stat-label">Em uso</div><div class="stat-val blue">${uso}</div><div class="stat-unit">relatórios</div></div>
      <div class="stat-item"><div class="stat-label">Pendente</div><div class="stat-val" style="color:var(--pastel-orange)">${pend}</div><div class="stat-unit">relatórios</div></div>
      <div class="stat-item"><div class="stat-label">Entregues</div><div class="stat-val green">${ok}</div><div class="stat-unit">relatórios</div></div>`;
    return;
  }
  if (currentMeta().fixedModel) {
    grid.innerHTML = `
      <div class="stat-item"><div class="stat-label">${currentMeta().label}</div><div class="stat-val blue">${items.length}</div><div class="stat-unit">unidades</div></div>
      <div class="stat-item"><div class="stat-label">Modelo</div><div class="stat-val" style="font-size:15px;color:var(--pastel-purple)">${window.PROATI.tabletModel}</div><div class="stat-unit">único da escola</div></div>
      <div class="stat-item"><div class="stat-label">Aba</div><div class="stat-val green">${currentMeta().label.toUpperCase()}</div><div class="stat-unit">inventário</div></div>`;
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
  grid.innerHTML = `
    <div class="stat-item"><div class="stat-label">Total</div><div class="stat-val yellow">${items.length}</div><div class="stat-unit">unidades</div></div>
    <div class="stat-item"><div class="stat-label">Perfeito estado</div><div class="stat-val green">${ok}</div><div class="stat-unit">unidades</div></div>
    <div class="stat-item"><div class="stat-label">Danos periféricos</div><div class="stat-val blue">${peri}</div><div class="stat-unit">unidades</div></div>`;
}

function showActionsColumn() {
  if (isGestao()) {
    return true;
  }
  return Boolean(window.PROATI.canEdit);
}

function renderHead() {
  if (isGestao()) {
    $("equip-head").innerHTML = `<tr>
      <th class="th-n">#</th>
      <th class="th-tab">Modelos</th>
      <th>Quantidade</th>
      <th>Quantidade atual</th>
      <th>Sala</th>
      <th>Professor</th>
      <th style="text-align:center">Transferências</th>
      <th style="text-align:center">Status</th>
      ${showActionsColumn() ? `<th style="width:220px">Ações</th>` : ""}
    </tr>`;
    return;
  }
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
  if (isGestao()) {
    const actionsOn = showActionsColumn();
    if (!items.length) {
      body.innerHTML = `<tr><td colspan="${actionsOn ? 9 : 8}" class="empty">Nenhum relatório registrado.</td></tr>`;
      return;
    }
    body.innerHTML = items
      .map((item, idx) => {
        const buttons = [
          `<button class="btn-sm btn-more" data-details="${item.id}" type="button" title="Detalhes das alterações">︙</button>`,
        ];
        if (item.can_alter) buttons.push(`<button class="btn-sm" data-alter="${item.id}" type="button">Alterar</button>`);
        if (item.can_delete) buttons.push(`<button class="btn-sm btn-danger" data-del-report="${item.id}" type="button">Excluir</button>`);
        const actions = actionsOn
          ? `<td class="actions-cell">${buttons.join("")}</td>`
          : "";
        const transferencias = (item.movimentos || []).filter((move) => move.tipo === "Transferido").length;
        return `<tr>
          <td class="td-num"><span class="num-badge">${idx + 1}</span></td>
          <td class="td-tab">${escapeHtml(item.modelos)}</td>
          <td>${escapeHtml(item.quantidade)}</td>
          <td>${escapeHtml(item.quantidade_atual)}</td>
          <td>${escapeHtml(item.sala)}</td>
          <td>${escapeHtml(item.professor)}</td>
          <td style="text-align:center">${transferencias}</td>
          <td style="text-align:center"><span class="badge ${badgeClass(item.status)}">${escapeHtml(item.status)}</span></td>
          ${actions}
        </tr>`;
      })
      .join("");
    return;
  }
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

async function loadReports() {
  const data = await request(`/api/relatorios?tab=${encodeURIComponent(state.tab)}`);
  state.items = data.itens || [];
  renderStats(state.items);
  renderHead();
  renderRows(state.items);
}

async function loadTab() {
  if (isGestao()) {
    await loadReports();
    return;
  }
  await loadEquipment();
}

function syncAddButton() {
  const addBtn = $("btn-add");
  if (!addBtn) return;
  if (isGestao()) {
    addBtn.style.display = window.PROATI.isProfessor || window.PROATI.isAdmin ? "" : "none";
    addBtn.textContent = "+ ADICIONAR RELATÓRIO";
    return;
  }
  addBtn.style.display = window.PROATI.canEdit ? "" : "none";
  addBtn.textContent = "+ ADICIONAR";
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

function lastOpenReport() {
  return (state.items || []).find((item) => item.status === "Em uso" && item.mine);
}

function openReportKindModal() {
  $("report-kind-modal").classList.add("open");
}

function closeReportKindModal() {
  $("report-kind-modal").classList.remove("open");
}

function openReportModal() {
  closeReportKindModal();
  $("r-modelos").value = "";
  $("r-quantidade").value = "";
  $("r-sala").value = "";
  $("report-modal").classList.add("open");
}

function closeReportModal() {
  $("report-modal").classList.remove("open");
}

async function saveReport(event) {
  event.preventDefault();
  try {
    await request("/api/relatorios", {
      method: "POST",
      body: JSON.stringify({
        tab: state.tab,
        modelos: $("r-modelos").value.trim(),
        quantidade: $("r-quantidade").value,
        sala: $("r-sala").value.trim(),
      }),
    });
    showToast("✔ Relatório de retirada adicionado");
    closeReportModal();
    await loadReports();
  } catch (err) {
    showToast("✘ " + err.message);
  }
}

function openReturnModal() {
  const item = lastOpenReport();
  closeReportKindModal();
  if (!item) {
    showToast("✘ Não há relatório em uso para devolver.");
    return;
  }
  $("rd-id").value = item.id;
  $("rd-modelos").value = item.modelos || "";
  $("rd-quantidade").value = item.quantidade || "";
  $("rd-quantidade-atual").value = item.quantidade_atual || "";
  $("rd-ainda-com").checked = false;
  const hasDest = Boolean(item.destinatario);
  $("wrap-ainda-com").hidden = !hasDest;
  $("rd-ainda-com-label").textContent = hasDest
    ? `Os notebooks ainda estão com ${item.destinatario}`
    : "Os notebooks ainda estão com o destinatário";
  $("report-return-modal").classList.add("open");
}

function closeReturnModal() {
  $("report-return-modal").classList.remove("open");
}

async function saveReturnReport(event) {
  event.preventDefault();
  const id = $("rd-id").value;
  try {
    await request(`/api/relatorios/${id}/devolver`, {
      method: "POST",
      body: JSON.stringify({
        ainda_com_destinatario: Boolean($("rd-ainda-com").checked && !$("wrap-ainda-com").hidden),
      }),
    });
    showToast("✔ Relatório de devolução salvo");
    closeReturnModal();
    await loadReports();
  } catch (err) {
    showToast("✘ " + err.message);
  }
}

function isTransferLike(tipo) {
  return tipo === "Transferido" || tipo === "Coletado transferência";
}

function syncTransferFields() {
  const tipo = $("ra-tipo").value;
  const show = isTransferLike(tipo);
  const coletado = tipo === "Coletado transferência";
  $("wrap-destinatario").hidden = !show;
  $("wrap-sala-destino").hidden = !show;
  $("ra-destinatario").required = show;
  $("ra-sala-destino").required = show;
  $("ra-person-label").textContent = coletado ? "Remetente" : "Destinatário";
  $("ra-quantidade").placeholder = coletado ? "Quantidade a somar" : "Quantidade a baixar";
  const item = state.items.find((row) => String(row.id) === String($("ra-id").value));
  if (item) {
    const atual = Number(item.quantidade_atual) || 0;
    const inicial = Number(item.quantidade) || 0;
    $("ra-quantidade").max = coletado ? Math.max(inicial - atual, 1) : Math.max(atual, 1);
  }
  if (!show) {
    $("ra-destinatario").value = "";
    $("ra-sala-destino").value = "";
  }
}

function openAlterModal(item) {
  $("ra-id").value = item.id;
  $("ra-quantidade").value = "";
  $("ra-tipo").value = "Entregue";
  $("ra-destinatario").value = "";
  $("ra-sala-destino").value = "";
  syncTransferFields();
  $("report-alter-modal").classList.add("open");
}

function closeAlterModal() {
  $("report-alter-modal").classList.remove("open");
}

async function saveAlterReport(event) {
  event.preventDefault();
  const id = $("ra-id").value;
  const tipo = $("ra-tipo").value;
  const payload = {
    quantidade: $("ra-quantidade").value,
    tipo,
  };
  if (isTransferLike(tipo)) {
    const pessoa = $("ra-destinatario").value.trim();
    payload.sala_destino = $("ra-sala-destino").value.trim();
    if (tipo === "Coletado transferência") payload.remetente = pessoa;
    else payload.destinatario = pessoa;
  }
  try {
    await request(`/api/relatorios/${id}/alterar`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showToast("✔ Relatório alterado");
    closeAlterModal();
    await loadReports();
  } catch (err) {
    showToast("✘ " + err.message);
  }
}

async function removeReport(id) {
  if (!confirm("Excluir este relatório?")) return;
  try {
    await request(`/api/relatorios/${id}`, { method: "DELETE" });
    showToast("✔ Relatório excluído");
    await loadReports();
  } catch (err) {
    showToast("✘ " + err.message);
  }
}

function openDetailsModal(item) {
  const list = $("report-details-list");
  const moves = item.movimentos || [];
  if (!moves.length) {
    list.innerHTML = `<p class="admin-hint">Nenhuma alteração registrada neste relatório.</p>`;
  } else {
    list.innerHTML = moves
      .map((move) => {
        const extra = [];
        if (move.quantidade) extra.push(`Quantidade: ${escapeHtml(move.quantidade)}`);
        if (move.destinatario) {
          const personLabel = move.tipo === "Coletado transferência" ? "Remetente" : "Destinatário";
          extra.push(`${personLabel}: ${escapeHtml(move.destinatario)}`);
        }
        if (move.sala_destino) extra.push(`Sala de destino: ${escapeHtml(move.sala_destino)}`);
        if (move.detalhe) extra.push(escapeHtml(move.detalhe));
        return `<div class="history-item">
          <div class="history-when">${escapeHtml(move.quando)}</div>
          <div class="history-title">${escapeHtml(move.tipo)}</div>
          <div class="history-meta">Conta: ${escapeHtml(move.usuario)}${move.cargo ? " · " + escapeHtml(move.cargo) : ""}</div>
          ${extra.length ? `<div class="history-meta">${extra.join("<br>")}</div>` : ""}
        </div>`;
      })
      .join("");
  }
  $("report-details-modal").classList.add("open");
}

function closeDetailsModal() {
  $("report-details-modal").classList.remove("open");
}

function roleLabel(role) {
  const labels = window.PROATI.roleLabels || {};
  if (labels[role]) return labels[role];
  const map = {
    vgs_owner: "VGS-Owner's",
    super_admin: "Super Admin",
    admin: "Admin",
    proati: "Proati",
    coordenador: "Coordenador",
    professor: "Professor",
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
  const assignable = data.assignable_roles || window.PROATI.roles || [];
  state.users = data.usuarios;
  state.assignableRoles = assignable;
  body.innerHTML = data.usuarios
    .map((user) => {
      const pending = user.must_reset_password
        ? `<span class="badge badge-yellow">Aguardando senha</span>`
        : "";
      let cargo = `<span class="badge badge-${user.role}">${roleLabel(user.role)}</span>`;
      if (user.is_self) {
        cargo += `<span class="text-muted">Sua conta</span>`;
      } else if (user.can_edit_role) {
        cargo += `<button class="btn-sm btn-save-role" data-edit-role="${user.id}" type="button">Alterar cargo</button>`;
      }
      const resetBtn = user.can_reset
        ? `<button class="btn-sm btn-warning" data-reset="${user.id}" type="button">Redefinir senha</button>`
        : "";
      const delBtn = user.can_manage
        ? `<button class="btn-sm btn-danger" data-del-user="${user.id}" type="button">Excluir conta</button>`
        : "";
      return `<tr>
        <td><strong>${escapeHtml(user.username)}</strong> ${pending}</td>
        <td>${escapeHtml(user.email)}</td>
        <td><div class="cargo-cell">${cargo}</div></td>
        <td>
          <div class="actions-stack">
            ${resetBtn}
            ${delBtn}
          </div>
        </td>
      </tr>`;
    })
    .join("");
}

function openRoleModal(userId) {
  const user = state.users.find((item) => String(item.id) === String(userId));
  const modal = $("role-modal");
  if (!user || !modal) return;
  state.roleUserId = user.id;
  state.pickedRole = user.role;
  $("role-user-label").textContent = `${user.username} · ${user.email}`;
  const roles = [...new Set([user.role, ...(state.assignableRoles || [])])];
  $("role-options").innerHTML = roles
    .map(
      (role) => `<button class="role-option${role === user.role ? " selected" : ""}" type="button" data-pick-role="${role}">
        <span class="badge badge-${role}">${roleLabel(role)}</span>
        <span class="role-check">✓</span>
      </button>`
    )
    .join("");
  modal.classList.add("open");
}

function closeRoleModal() {
  const modal = $("role-modal");
  if (modal) modal.classList.remove("open");
}

function pickRole(role) {
  state.pickedRole = role;
  document.querySelectorAll(".role-option").forEach((btn) => {
    btn.classList.toggle("selected", btn.dataset.pickRole === role);
  });
}

async function saveRole() {
  if (!state.roleUserId || !state.pickedRole) return;
  try {
    await request(`/api/usuarios/${state.roleUserId}/cargo`, {
      method: "POST",
      body: JSON.stringify({ role: state.pickedRole }),
    });
    showToast("✔ Cargo atualizado");
    closeRoleModal();
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

function openUserModal() {
  const modal = $("user-modal");
  const form = $("user-form");
  if (!modal || !form) {
    showToast("✘ Painel de cadastro indisponível");
    return;
  }
  form.reset();
  const role = $("u-role");
  if (role) {
    const hasViewer = Array.from(role.options).some((opt) => opt.value === "visualizador");
    role.value = hasViewer ? "visualizador" : (role.options[0] ? role.options[0].value : "");
  }
  modal.classList.add("open");
}

function closeUserModal() {
  const modal = $("user-modal");
  if (modal) modal.classList.remove("open");
}

async function saveNewUser(event) {
  event.preventDefault();
  try {
    await request("/api/usuarios", {
      method: "POST",
      body: JSON.stringify({
        username: $("u-username").value.trim(),
        email: $("u-email").value.trim(),
        password: $("u-password").value,
        confirm_password: $("u-confirm").value,
        role: $("u-role").value,
      }),
    });
    showToast("✔ Usuário adicionado");
    closeUserModal();
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
        <td><span class="badge ${row.strike_level >= 6 ? "badge-n" : "badge-yellow"}">${escapeHtml(row.level_label)}</span></td>
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

function overflowTabs() {
  return window.PROATI.overflowTabs || [];
}

function closeMoreMenu() {
  const panel = $("nav-more-panel");
  const btn = $("nav-more-btn");
  if (panel) panel.hidden = true;
  if (btn) btn.setAttribute("aria-expanded", "false");
}

function toggleMoreMenu(event) {
  event.preventDefault();
  event.stopPropagation();
  const panel = $("nav-more-panel");
  const btn = $("nav-more-btn");
  if (!panel || !btn) return;
  const shouldOpen = panel.hidden;
  panel.hidden = !shouldOpen;
  btn.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
}

function showView(tab) {
  state.tab = tab;
  const inOverflow = overflowTabs().includes(tab);
  document.querySelectorAll(".nav-tab").forEach((btn) => {
    if (btn.id === "nav-more-btn") {
      btn.classList.toggle("active", inOverflow);
      return;
    }
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  document.querySelectorAll(".nav-more-row").forEach((row) => {
    row.classList.toggle("active", row.dataset.tab === tab);
  });
  closeMoreMenu();
  const isAdminTab = tab === "admin";
  $("view-inventory").classList.toggle("active", !isAdminTab);
  const adminView = $("view-admin");
  if (adminView) adminView.classList.toggle("active", isAdminTab);
  if (isAdminTab) {
    Promise.all([loadUsers(), loadBlocks()]).catch((err) => showToast("✘ " + err.message));
    return;
  }
  $("tab-label").textContent = currentMeta().label.toUpperCase();
  syncAddButton();
  loadTab().catch((err) => showToast("✘ " + err.message));
}

document.querySelectorAll(".nav-tab").forEach((btn) => {
  if (btn.id === "nav-more-btn") return;
  btn.addEventListener("click", () => showView(btn.dataset.tab));
});

const moreBtn = $("nav-more-btn");
if (moreBtn) {
  moreBtn.addEventListener("click", toggleMoreMenu);
  document.querySelectorAll(".nav-more-row").forEach((row) => {
    row.addEventListener("click", () => showView(row.dataset.tab));
  });
  document.addEventListener("click", (event) => {
    const wrap = $("nav-more");
    if (wrap && !wrap.contains(event.target)) closeMoreMenu();
  });
}

const addBtn = $("btn-add");
if (addBtn) {
  addBtn.addEventListener("click", () => {
    if (isGestao()) openReportKindModal();
    else openModal(null);
  });
}
$("modal-close").addEventListener("click", closeModal);
$("modal-cancel").addEventListener("click", closeModal);
$("equip-modal").addEventListener("click", (e) => {
  if (e.target.id === "equip-modal") closeModal();
});
$("equip-form").addEventListener("submit", saveEquipment);
$("equip-body").addEventListener("click", (e) => {
  const detailsBtn = e.target.closest("[data-details]");
  const editId = e.target.dataset.edit;
  const delId = e.target.dataset.del;
  const alterId = e.target.dataset.alter;
  const delReportId = e.target.dataset.delReport;
  if (detailsBtn) {
    const item = state.items.find((i) => String(i.id) === String(detailsBtn.dataset.details));
    if (item) openDetailsModal(item);
    return;
  }
  if (editId) {
    const item = state.items.find((i) => String(i.id) === String(editId));
    if (item) openModal(item);
  }
  if (delId) removeEquipment(delId);
  if (alterId) {
    const item = state.items.find((i) => String(i.id) === String(alterId));
    if (item) openAlterModal(item);
  }
  if (delReportId) removeReport(delReportId);
});

$("report-modal-close").addEventListener("click", closeReportModal);
$("report-modal-cancel").addEventListener("click", closeReportModal);
$("report-modal").addEventListener("click", (e) => {
  if (e.target.id === "report-modal") closeReportModal();
});
$("report-form").addEventListener("submit", saveReport);

$("report-kind-close").addEventListener("click", closeReportKindModal);
$("report-kind-cancel").addEventListener("click", closeReportKindModal);
$("report-kind-modal").addEventListener("click", (e) => {
  if (e.target.id === "report-kind-modal") closeReportKindModal();
  const kind = e.target.closest("[data-report-kind]");
  if (!kind) return;
  if (kind.dataset.reportKind === "retirada") openReportModal();
  else openReturnModal();
});

$("report-return-close").addEventListener("click", closeReturnModal);
$("report-return-cancel").addEventListener("click", closeReturnModal);
$("report-return-modal").addEventListener("click", (e) => {
  if (e.target.id === "report-return-modal") closeReturnModal();
});
$("report-return-form").addEventListener("submit", saveReturnReport);

$("report-alter-close").addEventListener("click", closeAlterModal);
$("report-alter-cancel").addEventListener("click", closeAlterModal);
$("report-alter-modal").addEventListener("click", (e) => {
  if (e.target.id === "report-alter-modal") closeAlterModal();
});
$("report-alter-form").addEventListener("submit", saveAlterReport);
$("ra-tipo").addEventListener("change", syncTransferFields);

$("report-details-close").addEventListener("click", closeDetailsModal);
$("report-details-cancel").addEventListener("click", closeDetailsModal);
$("report-details-modal").addEventListener("click", (e) => {
  if (e.target.id === "report-details-modal") closeDetailsModal();
});

const usersBody = $("users-body");
if (usersBody) {
  usersBody.addEventListener("click", (e) => {
    const editRoleBtn = e.target.closest("[data-edit-role]");
    const delBtn = e.target.closest("[data-del-user]");
    const resetBtn = e.target.closest("[data-reset]");
    if (editRoleBtn) openRoleModal(editRoleBtn.dataset.editRole);
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

const roleModal = $("role-modal");
if (roleModal) {
  $("role-modal-close").addEventListener("click", closeRoleModal);
  $("role-modal-cancel").addEventListener("click", closeRoleModal);
  $("role-modal-save").addEventListener("click", saveRole);
  $("role-options").addEventListener("click", (e) => {
    const pick = e.target.closest("[data-pick-role]");
    if (pick) pickRole(pick.dataset.pickRole);
  });
  roleModal.addEventListener("click", (e) => {
    if (e.target.id === "role-modal") closeRoleModal();
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

const addUserBtn = $("btn-add-user");
if (addUserBtn) {
  addUserBtn.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    openUserModal();
  });
}
const userModal = $("user-modal");
if (userModal) {
  $("user-modal-close").addEventListener("click", closeUserModal);
  $("user-modal-cancel").addEventListener("click", closeUserModal);
  $("user-form").addEventListener("submit", saveNewUser);
  userModal.addEventListener("click", (e) => {
    if (e.target.id === "user-modal") closeUserModal();
  });
}

showView(window.PROATI.defaultTab || "tablets");
