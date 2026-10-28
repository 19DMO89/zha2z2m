// Sidebar panel of the ZHA → Zigbee2MQTT migration helper.
// Plain web component (no build step); talks to the zha2z2m/* websocket API.

const TEXT = {
  en: {
    title: "ZHA → Zigbee2MQTT",
    refresh: "Refresh",
    step_export: "Export ZHA",
    step_disable: "Disable ZHA",
    step_pair: "Pair in Zigbee2MQTT",
    step_migrate: "Migrate devices",
    step_refs: "Check references",
    exported_at: "Exported",
    not_exported: "Not exported yet",
    export: "Export now",
    export_again: "Export again",
    export_hint: "Saves all ZHA devices and entities to /config/zha2z2m/. Run it while ZHA is still active so the network settings are exported too.",
    zha_active: "ZHA is active",
    zha_inactive: "ZHA is disabled",
    zha_missing: "ZHA is not installed",
    disable_zha: "Disable ZHA",
    enable_zha: "Enable ZHA again",
    confirm_disable: "Disable ZHA now? Zigbee2MQTT can only use the coordinator after ZHA is disabled.",
    confirm_enable: "Enable ZHA again? Stop Zigbee2MQTT first!",
    coordinator: "Coordinator",
    z2m_setup: "Zigbee2MQTT setting",
    new_devices: "New Zigbee2MQTT devices",
    no_new_devices: "No unmigrated Zigbee2MQTT devices yet. Pair your devices in Zigbee2MQTT – they will show up here.",
    was_zha: "Was in ZHA",
    choose: "– choose –",
    map: "Assign entities",
    migrate: "Migrate",
    cancel: "Cancel",
    auto: "Migrate all with same IEEE",
    same_ieee: "same IEEE",
    old_entity: "ZHA entity (keeps its entity id)",
    new_entity: "Zigbee2MQTT entity",
    skip: "– skip –",
    preserve_names: "Take over device name and exact entity names",
    copy_areas: "Take over areas and labels",
    zha_devices: "ZHA devices from the export",
    search: "Search…",
    migrated: "migrated",
    pending: "pending",
    found: "found in Z2M",
    entities: "entities",
    refs: "References",
    refs_hint: "Entity ids are taken over. Only things that use a device id (device triggers/actions, target: device_id) need attention.",
    check: "Check",
    replace: "Replace old device ids in YAML (with backup)",
    nothing_found: "Nothing found ✓",
    rebuild: "rebuild by hand",
    old_ids: "old device id(s)",
    automations: "Automations using old device ids",
    scripts: "Scripts using old device ids",
    result: "Result",
    renamed: "taken over",
    skipped: "skipped",
    failed: "failed",
    progress: "migrated",
    need_export: "Export ZHA first.",
    need_disable: "Disable ZHA before migrating.",
    duplicate: "A Zigbee2MQTT entity is selected more than once.",
  },
  de: {
    title: "ZHA → Zigbee2MQTT",
    refresh: "Aktualisieren",
    step_export: "ZHA exportieren",
    step_disable: "ZHA deaktivieren",
    step_pair: "In Zigbee2MQTT anlernen",
    step_migrate: "Geräte migrieren",
    step_refs: "Verweise prüfen",
    exported_at: "Exportiert",
    not_exported: "Noch nicht exportiert",
    export: "Jetzt exportieren",
    export_again: "Erneut exportieren",
    export_hint: "Speichert alle ZHA-Geräte und -Entitäten nach /config/zha2z2m/. Solange ZHA noch aktiv ist, werden auch die Netzwerkeinstellungen exportiert.",
    zha_active: "ZHA ist aktiv",
    zha_inactive: "ZHA ist deaktiviert",
    zha_missing: "ZHA ist nicht installiert",
    disable_zha: "ZHA deaktivieren",
    enable_zha: "ZHA wieder aktivieren",
    confirm_disable: "ZHA jetzt deaktivieren? Zigbee2MQTT kann den Koordinator erst danach verwenden.",
    confirm_enable: "ZHA wieder aktivieren? Vorher Zigbee2MQTT stoppen!",
    coordinator: "Koordinator",
    z2m_setup: "Zigbee2MQTT-Einstellung",
    new_devices: "Neue Zigbee2MQTT-Geräte",
    no_new_devices: "Noch keine unmigrierten Zigbee2MQTT-Geräte. Lerne deine Geräte in Zigbee2MQTT an – sie erscheinen dann hier.",
    was_zha: "War in ZHA",
    choose: "– auswählen –",
    map: "Entitäten zuordnen",
    migrate: "Migrieren",
    cancel: "Abbrechen",
    auto: "Alle mit gleicher IEEE migrieren",
    same_ieee: "gleiche IEEE",
    old_entity: "ZHA-Entität (behält ihre Entitäts-ID)",
    new_entity: "Zigbee2MQTT-Entität",
    skip: "– überspringen –",
    preserve_names: "Gerätename und exakte Entitätsnamen übernehmen",
    copy_areas: "Bereiche und Labels übernehmen",
    zha_devices: "ZHA-Geräte aus dem Export",
    search: "Suchen…",
    migrated: "migriert",
    pending: "ausstehend",
    found: "in Z2M gefunden",
    entities: "Entitäten",
    refs: "Verweise",
    refs_hint: "Entitäts-IDs werden übernommen. Nur was eine Geräte-ID verwendet (Geräte-Auslöser/-Aktionen, target: device_id), braucht Aufmerksamkeit.",
    check: "Prüfen",
    replace: "Alte Geräte-IDs in YAML ersetzen (mit Backup)",
    nothing_found: "Nichts gefunden ✓",
    rebuild: "von Hand neu bauen",
    old_ids: "alte Geräte-ID(s)",
    automations: "Automationen mit alten Geräte-IDs",
    scripts: "Skripte mit alten Geräte-IDs",
    result: "Ergebnis",
    renamed: "übernommen",
    skipped: "übersprungen",
    failed: "fehlgeschlagen",
    progress: "migriert",
    need_export: "Bitte zuerst ZHA exportieren.",
    need_disable: "Bitte vor dem Migrieren ZHA deaktivieren.",
    duplicate: "Eine Zigbee2MQTT-Entität ist mehrfach ausgewählt.",
  },
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

class Zha2Z2MPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._status = null;
    this._choice = {};
    this._edit = null;
    this._refs = null;
    this._result = null;
    this._error = null;
    this._busy = false;
    this._filter = "";
    this._options = { preserve_names: true, copy_areas: true };
    this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    this.shadowRoot.addEventListener("change", (ev) => this._onChange(ev));
    this.shadowRoot.addEventListener("input", (ev) => this._onInput(ev));
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (this._menu) this._menu.hass = hass;
    if (first) this._load();
  }

  set narrow(narrow) {
    this._narrow = narrow;
    if (this._menu) this._menu.narrow = narrow;
  }

  set panel(panel) {
    this._panel = panel;
  }

  connectedCallback() {
    if (this._hass) this._load();
    else this._render();
  }

  get _t() {
    const lang = (this._hass?.language || "en").slice(0, 2);
    return TEXT[lang] || TEXT.en;
  }

  _ws(type, data = {}) {
    return this._hass.callWS({ type: `zha2z2m/${type}`, ...data });
  }

  async _run(fn) {
    this._busy = true;
    this._error = null;
    this._render();
    try {
      await fn();
    } catch (err) {
      this._error = this._errorText(err);
    }
    this._busy = false;
    await this._load();
  }

  _errorText(err) {
    const t = this._t;
    const code = err?.code || err?.message;
    return { export_first: t.need_export, zha_active: t.need_disable, duplicate_target: t.duplicate }[code] || err?.message || String(err);
  }

  async _load() {
    try {
      this._status = await this._ws("status");
    } catch (err) {
      this._error = this._errorText(err);
    }
    this._render();
  }

  // ------------------------------------------------------------ events

  _onClick(ev) {
    const el = ev.target.closest("[data-action]");
    if (!el || this._busy) return;
    const t = this._t;
    const { action, id } = el.dataset;
    switch (action) {
      case "refresh":
        this._load();
        break;
      case "export":
        this._run(async () => {
          const r = await this._ws("export");
          this._result = { title: t.step_export, lines: [`✅ ${r.devices} / ${r.entities} ${t.entities}`, r.file] };
        });
        break;
      case "disable":
        if (confirm(t.confirm_disable)) this._run(() => this._ws("set_zha", { enabled: false }));
        break;
      case "enable":
        if (confirm(t.confirm_enable)) this._run(() => this._ws("set_zha", { enabled: true }));
        break;
      case "map": {
        const ieee = this._choice[id];
        if (!ieee) return;
        this._run(async () => {
          const s = await this._ws("suggest", { ieee, z2m_device_id: id });
          this._edit = { deviceId: id, ieee, ...s };
        });
        break;
      }
      case "cancel":
        this._edit = null;
        this._render();
        break;
      case "migrate": {
        const e = this._edit;
        this._run(async () => {
          const r = await this._ws("migrate", { ieee: e.ieee, z2m_device_id: e.deviceId, mapping: e.mapping, ...this._options });
          this._edit = null;
          this._result = this._resultBlock([r]);
        });
        break;
      }
      case "auto":
        this._run(async () => {
          const r = await this._ws("auto_migrate", this._options);
          this._result = this._resultBlock(r.results);
        });
        break;
      case "refs":
        this._run(async () => {
          this._refs = await this._ws("references");
        });
        break;
      case "replace":
        this._run(async () => {
          this._refs = await this._ws("replace_references");
          this._result = { title: t.refs, lines: [this._refs.changed.length ? `✅ ${this._refs.changed.join(", ")}` : t.nothing_found] };
        });
        break;
      case "close-result":
        this._result = null;
        this._render();
        break;
    }
  }

  _onChange(ev) {
    const el = ev.target;
    if (el.dataset.choice) this._choice[el.dataset.choice] = el.value;
    if (el.dataset.map && this._edit) this._edit.mapping[el.dataset.map] = el.value;
    if (el.dataset.option) this._options[el.dataset.option] = el.checked;
    if (el.dataset.choice) this._render();
  }

  _onInput(ev) {
    if (ev.target.dataset.filter === undefined) return;
    this._filter = ev.target.value.toLowerCase();
    this._renderZhaList();
  }

  _resultBlock(results) {
    const t = this._t;
    const lines = [];
    for (const r of results) {
      if (r.error) {
        lines.push(`❌ ${r.ieee}: ${this._errorText({ code: r.error })}`);
        continue;
      }
      lines.push(`<b>${esc(r.device)}</b> (${esc(r.ieee)}) – ${r.renamed.length} ${t.renamed}, ${r.skipped.length} ${t.skipped}, ${r.failed.length} ${t.failed}`);
      for (const x of r.renamed) lines.push(`&nbsp;&nbsp;✅ <code>${esc(x.from)}</code> → <code>${esc(x.to)}</code>`);
      for (const x of r.failed) lines.push(`&nbsp;&nbsp;❌ <code>${esc(x.entity_id)}</code>: ${esc(x.reason)}`);
      const refs = [...(r.references.automations || []), ...(r.references.scripts || [])];
      if (refs.length) lines.push(`&nbsp;&nbsp;⚠️ ${refs.map((x) => `<code>${esc(x)}</code>`).join(", ")}`);
    }
    return { title: t.result, lines, html: true };
  }

  // ------------------------------------------------------------ render

  _render() {
    const t = this._t;
    const s = this._status;
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <div class="toolbar">
        <span id="menu"></span>
        <div class="title">${t.title}</div>
        ${s ? `<span class="version">v${esc(s.version)}</span>` : ""}
        <button class="icon" data-action="refresh" title="${t.refresh}">⟳</button>
      </div>
      <div class="content ${this._busy ? "busy" : ""}">
        ${this._error ? `<div class="alert error">${esc(this._error)}</div>` : ""}
        ${this._result ? this._renderResult() : ""}
        ${s ? this._renderSteps(s) + this._renderNewDevices(s) + this._renderZha(s) + this._renderRefs(s) : `<div class="card">…</div>`}
      </div>`;

    if (!this._menu) {
      this._menu = document.createElement("ha-menu-button");
    }
    this._menu.hass = this._hass;
    this._menu.narrow = this._narrow;
    this.shadowRoot.getElementById("menu").appendChild(this._menu);
    this._renderZhaList();
  }

  _renderResult() {
    const r = this._result;
    const lines = r.html ? r.lines : r.lines.map(esc);
    return `<div class="alert ok"><div class="row"><b>${esc(r.title)}</b><span class="grow"></span><button class="icon" data-action="close-result">✕</button></div>${lines.join("<br>")}</div>`;
  }

  _renderSteps(s) {
    const t = this._t;
    const total = s.zha_devices.length;
    const done = s.zha_devices.filter((d) => d.migrated).length;
    const waiting = s.z2m_devices.filter((d) => !d.migrated).length;
    const pct = total ? Math.round((done / total) * 100) : 0;
    const step = (ok, n, label, detail) =>
      `<div class="step ${ok ? "ok" : ""}"><span class="num">${ok ? "✓" : n}</span><div><div>${label}</div><div class="muted">${detail}</div></div></div>`;
    const zhaState = !s.zha_installed ? t.zha_missing : s.zha_active ? t.zha_active : t.zha_inactive;
    const zha = s.zha || {};
    return `
      <div class="card">
        <div class="steps">
          ${step(!!s.exported_at, 1, t.step_export, s.exported_at ? `${t.exported_at}: ${new Date(s.exported_at).toLocaleString()}` : t.not_exported)}
          ${step(!s.zha_active && !!s.exported_at, 2, t.step_disable, zhaState)}
          ${step(waiting > 0 || done > 0, 3, t.step_pair, `${waiting} ${t.new_devices}`)}
          ${step(total > 0 && done === total, 4, t.step_migrate, `${done} / ${total} ${t.progress}`)}
        </div>
        <div class="bar"><div style="width:${pct}%"></div></div>
        <div class="row wrap">
          <button data-action="export" class="${s.exported_at ? "" : "primary"}" ${s.zha_installed ? "" : "disabled"}>${s.exported_at ? t.export_again : t.export}</button>
          ${s.zha_active
            ? `<button data-action="disable" class="${s.exported_at ? "primary" : ""}" ${s.exported_at ? "" : "disabled"}>${t.disable_zha}</button>`
            : s.zha_installed ? `<button data-action="enable">${t.enable_zha}</button>` : ""}
        </div>
        <p class="muted">${t.export_hint}</p>
        ${zha.port ? `<p class="muted">${t.coordinator}: <code>${esc(zha.port)}</code> (${esc(zha.radio_type)}) → ${t.z2m_setup}: <code>adapter: ${esc(zha.z2m_adapter || "?")}</code></p>` : ""}
      </div>`;
  }

  _renderNewDevices(s) {
    const t = this._t;
    const pending = s.zha_devices.filter((d) => !d.migrated).sort((a, b) => a.name.localeCompare(b.name));
    const devices = s.z2m_devices.filter((d) => !d.migrated).sort((a, b) => a.name.localeCompare(b.name));
    const autoCount = devices.filter((d) => d.match).length;
    const blocked = !s.exported_at || s.zha_active;
    const rows = devices
      .map((d) => {
        if (this._choice[d.device_id] === undefined && d.match) this._choice[d.device_id] = d.match;
        const chosen = this._choice[d.device_id] || "";
        const options = pending
          .map((z) => `<option value="${esc(z.ieee)}" ${z.ieee === chosen ? "selected" : ""}>${esc(z.name)}${z.model ? ` – ${esc(z.model)}` : ""}${z.ieee === d.ieee ? ` ✓ ${t.same_ieee}` : ""}</option>`)
          .join("");
        const editing = this._edit && this._edit.deviceId === d.device_id;
        return `
          <div class="device ${editing ? "editing" : ""}">
            <div class="row wrap">
              <div class="grow">
                <div><b>${esc(d.name)}</b> ${d.match ? `<span class="chip ok">${t.same_ieee}</span>` : ""}</div>
                <div class="muted">${esc(d.ieee_display)} · ${esc(d.manufacturer || "")} ${esc(d.model || "")}</div>
              </div>
              <label class="select">${t.was_zha}
                <select data-choice="${esc(d.device_id)}" ${blocked ? "disabled" : ""}>
                  <option value="">${t.choose}</option>${options}
                </select>
              </label>
              <button data-action="map" data-id="${esc(d.device_id)}" ${chosen && !blocked ? "" : "disabled"}>${t.map}</button>
            </div>
            ${editing ? this._renderEditor() : ""}
          </div>`;
      })
      .join("");
    return `
      <div class="card">
        <div class="row wrap">
          <h2 class="grow">${t.new_devices}</h2>
          <button data-action="auto" class="primary" ${autoCount && !blocked ? "" : "disabled"}>${t.auto} (${autoCount})</button>
        </div>
        ${blocked ? `<p class="muted">${!s.exported_at ? t.need_export : t.need_disable}</p>` : ""}
        <div class="row wrap options">
          <label><input type="checkbox" data-option="preserve_names" ${this._options.preserve_names ? "checked" : ""}> ${t.preserve_names}</label>
          <label><input type="checkbox" data-option="copy_areas" ${this._options.copy_areas ? "checked" : ""}> ${t.copy_areas}</label>
        </div>
        ${rows || `<p class="muted">${t.no_new_devices}</p>`}
      </div>`;
  }

  _renderEditor() {
    const t = this._t;
    const e = this._edit;
    const rows = e.old_entities
      .map((old) => {
        const options = e.new_entities
          .filter((n) => n.domain === old.domain)
          .map((n) => `<option value="${esc(n.entity_id)}" ${e.mapping[old.entity_id] === n.entity_id ? "selected" : ""}>${esc(n.name)} (${esc(n.entity_id)})</option>`)
          .join("");
        return `
          <tr>
            <td><div>${esc(old.name)}</div><div class="muted"><code>${esc(old.entity_id)}</code></div></td>
            <td><select data-map="${esc(old.entity_id)}">
              <option value="${esc(e.skip)}" ${e.mapping[old.entity_id] === e.skip ? "selected" : ""}>${t.skip}</option>${options}
            </select></td>
          </tr>`;
      })
      .join("");
    return `
      <table>
        <thead><tr><th>${t.old_entity}</th><th>${t.new_entity}</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <div class="row end">
        <button data-action="cancel">${t.cancel}</button>
        <button data-action="migrate" class="primary">${t.migrate}</button>
      </div>`;
  }

  _renderZha(s) {
    const t = this._t;
    if (!s.zha_devices.length) return "";
    return `
      <div class="card">
        <div class="row wrap">
          <h2 class="grow">${t.zha_devices}</h2>
          <input type="search" data-filter placeholder="${t.search}" value="${esc(this._filter)}">
        </div>
        <div id="zha-list"></div>
      </div>`;
  }

  _renderZhaList() {
    const list = this.shadowRoot.getElementById("zha-list");
    const s = this._status;
    if (!list || !s) return;
    const t = this._t;
    const found = new Set(s.z2m_devices.map((d) => d.ieee));
    list.innerHTML = s.zha_devices
      .filter((d) => !this._filter || `${d.name} ${d.ieee_display} ${d.model} ${d.area_name}`.toLowerCase().includes(this._filter))
      .sort((a, b) => Number(a.migrated) - Number(b.migrated) || a.name.localeCompare(b.name))
      .map((d) => {
        const chip = d.migrated
          ? `<span class="chip ok">${t.migrated}</span>`
          : found.has(d.ieee)
            ? `<span class="chip info">${t.found}</span>`
            : `<span class="chip">${t.pending}</span>`;
        return `<div class="line"><div class="grow"><b>${esc(d.name)}</b><div class="muted">${esc(d.ieee_display)} · ${esc(d.manufacturer || "")} ${esc(d.model || "")}${d.area_name ? ` · ${esc(d.area_name)}` : ""} · ${d.entities} ${t.entities}</div></div>${chip}</div>`;
      })
      .join("");
  }

  _renderRefs(s) {
    const t = this._t;
    if (!s.zha_devices.some((d) => d.migrated)) return "";
    const r = this._refs;
    let body = "";
    if (r) {
      const files = Object.entries(r.files).map(([file, c]) => {
        const parts = [];
        if (c.device_ids) parts.push(`${c.device_ids}× ${t.old_ids}`);
        if (c.zha_device_automations) parts.push(`${c.zha_device_automations}× <code>domain: zha</code> (${t.rebuild})`);
        if (c.zha_event) parts.push(`${c.zha_event}× <code>zha_event</code> (${t.rebuild})`);
        return `<li><code>${esc(file)}</code>: ${parts.join(", ")}</li>`;
      });
      const name = (id) => esc(this._hass.states[id]?.attributes?.friendly_name || id);
      const list = (title, ids) => (ids.length ? `<p><b>${title}</b></p><ul>${ids.map((id) => `<li>${name(id)} <span class="muted">${esc(id)}</span></li>`).join("")}</ul>` : "");
      body = files.length || r.automations.length || r.scripts.length
        ? `<ul>${files.join("")}</ul>${list(t.automations, r.automations)}${list(t.scripts, r.scripts)}`
        : `<p>${t.nothing_found}</p>`;
    }
    return `
      <div class="card">
        <div class="row wrap">
          <h2 class="grow">${t.refs}</h2>
          <button data-action="refs">${t.check}</button>
          <button data-action="replace">${t.replace}</button>
        </div>
        <p class="muted">${t.refs_hint}</p>
        ${body}
      </div>`;
  }
}

const STYLE = `
  :host { display: block; background: var(--primary-background-color); color: var(--primary-text-color); min-height: 100vh; font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif); }
  .toolbar { display: flex; align-items: center; gap: 8px; height: var(--header-height, 56px); padding: 0 12px; background: var(--app-header-background-color, var(--primary-color)); color: var(--app-header-text-color, #fff); position: sticky; top: 0; z-index: 2; box-sizing: border-box; }
  .toolbar .title { font-size: 20px; flex: 1; }
  .toolbar .version { opacity: .7; font-size: 12px; }
  .toolbar .icon { color: inherit; }
  .content { max-width: 1000px; margin: 0 auto; padding: 16px; display: flex; flex-direction: column; gap: 16px; }
  .content.busy { opacity: .6; pointer-events: none; }
  .card { background: var(--card-background-color); border-radius: var(--ha-card-border-radius, 12px); box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,.1)); border: 1px solid var(--divider-color, transparent); padding: 16px; }
  h2 { margin: 0; font-size: 18px; font-weight: 500; }
  .row { display: flex; align-items: center; gap: 8px; }
  .row.wrap { flex-wrap: wrap; }
  .row.end { justify-content: flex-end; margin-top: 12px; }
  .grow { flex: 1; min-width: 0; }
  .muted { color: var(--secondary-text-color); font-size: 13px; }
  code { font-size: 12px; background: var(--secondary-background-color); padding: 1px 4px; border-radius: 4px; overflow-wrap: anywhere; }
  button { font: inherit; font-size: 14px; padding: 8px 14px; border-radius: 18px; border: 1px solid var(--primary-color); background: transparent; color: var(--primary-color); cursor: pointer; }
  button.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  button:disabled { opacity: .4; cursor: default; }
  button.icon { border: none; font-size: 18px; padding: 4px 8px; }
  select, input[type=search] { font: inherit; font-size: 14px; padding: 6px 8px; border-radius: 6px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); max-width: 100%; }
  label.select { display: flex; flex-direction: column; gap: 2px; font-size: 12px; color: var(--secondary-text-color); max-width: 100%; }
  .options { margin: 8px 0; font-size: 14px; gap: 16px; }
  .steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
  .step { display: flex; gap: 10px; align-items: flex-start; }
  .step .num { flex: none; width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; background: var(--secondary-background-color); font-weight: 500; }
  .step.ok .num { background: var(--success-color, #43a047); color: #fff; }
  .bar { height: 6px; border-radius: 3px; background: var(--secondary-background-color); margin: 16px 0; overflow: hidden; }
  .bar div { height: 100%; background: var(--success-color, #43a047); transition: width .3s; }
  .device { border-top: 1px solid var(--divider-color); padding: 12px 0; }
  .device.editing { background: var(--secondary-background-color); margin: 0 -16px; padding: 12px 16px; }
  .line { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-top: 1px solid var(--divider-color); }
  .chip { font-size: 12px; padding: 2px 8px; border-radius: 10px; background: var(--secondary-background-color); color: var(--secondary-text-color); white-space: nowrap; }
  .chip.ok { background: var(--success-color, #43a047); color: #fff; }
  .chip.info { background: var(--info-color, #039be5); color: #fff; }
  table { width: 100%; border-collapse: collapse; margin-top: 12px; }
  th { text-align: left; font-size: 12px; font-weight: 500; color: var(--secondary-text-color); padding: 4px; }
  td { padding: 6px 4px; border-top: 1px solid var(--divider-color); vertical-align: middle; }
  td select { width: 100%; }
  .alert { padding: 12px 16px; border-radius: 8px; font-size: 14px; line-height: 1.6; }
  .alert.error { background: var(--error-color, #db4437); color: #fff; }
  .alert.ok { background: var(--card-background-color); border-left: 4px solid var(--success-color, #43a047); }
  ul { margin: 8px 0; padding-left: 20px; }
  @media (max-width: 600px) { table, tbody, tr, td { display: block; } thead { display: none; } td { border: none; } tr { border-top: 1px solid var(--divider-color); padding: 6px 0; } }
`;

if (!customElements.get("zha2z2m-panel")) customElements.define("zha2z2m-panel", Zha2Z2MPanel);
