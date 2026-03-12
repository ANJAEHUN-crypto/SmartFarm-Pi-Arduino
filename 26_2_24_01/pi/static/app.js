(function () {
  const serialStatus = document.getElementById('serialStatus');
  const btnSerialToggle = document.getElementById('btnSerialToggle');
  const modal = document.getElementById('modal');
  const modalCh = document.getElementById('modalCh');
  const onTime = document.getElementById('onTime');
  const offTime = document.getElementById('offTime');
  const days = document.getElementById('days');
  const modalSave = document.getElementById('modalSave');
  const modalCancel = document.getElementById('modalCancel');

  let scheduleEdit = { channel: null, index: null };

  function setSerialStatus(open) {
    serialStatus.textContent = open ? '연결됨' : '연결 안 됨';
    serialStatus.classList.toggle('connected', open);
    btnSerialToggle.textContent = open ? '끊기' : '연결';
  }

  async function fetchSerialStatus() {
    try {
      const r = await fetch('/api/serial/status');
      const j = await r.json();
      setSerialStatus(j.open);
    } catch (_) {
      setSerialStatus(false);
    }
  }

  btnSerialToggle.addEventListener('click', async () => {
    const isOpen = serialStatus.classList.contains('connected');
    try {
      if (isOpen) {
        await fetch('/api/serial/close', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
      } else {
        await fetch('/api/serial/open', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      }
      await fetchSerialStatus();
      if (!isOpen) refreshState();
    } catch (e) {
      alert('시리얼 연결 실패: ' + e.message);
    }
  });

  async function refreshState() {
    try {
      const r = await fetch('/api/relay/state');
      const j = await r.json();
      if (j.ok && j.state && j.state.length === 4) {
        [1, 2, 3, 4].forEach((ch, i) => {
          const el = document.getElementById('state' + ch);
          if (!el) return;
          el.textContent = j.state[i] ? 'ON' : 'OFF';
          el.className = 'state ' + (j.state[i] ? 'on' : 'off');
        });
      }
    } catch (_) {}
  }

  document.querySelectorAll('.relay-card').forEach(function (card) {
    const ch = parseInt(card.dataset.ch, 10);
    card.querySelector('.on').addEventListener('click', async () => {
      try {
        const r = await fetch('/api/relay/on/' + ch, { method: 'POST' });
        const j = await r.json();
        if (j.ok) refreshState();
      } catch (e) { alert(e.message); }
    });
    card.querySelector('.off').addEventListener('click', async () => {
      try {
        const r = await fetch('/api/relay/off/' + ch, { method: 'POST' });
        const j = await r.json();
        if (j.ok) refreshState();
      } catch (e) { alert(e.message); }
    });
  });

  function renderSchedules(data) {
    [1, 2, 3, 4].forEach(ch => {
      const list = document.getElementById('list' + ch);
      if (!list) return;
      const arr = data.schedules && data.schedules[ch] ? data.schedules[ch] : [];
      list.innerHTML = arr.map((s, idx) =>
        '<li>' +
        '<span>' + s.on_time + ' ON → ' + s.off_time + ' OFF ' + (s.days && s.days !== 'daily' ? '(' + s.days + ')' : '') + '</span>' +
        '<span class="del" data-ch="' + ch + '" data-idx="' + idx + '">삭제</span>' +
        '</li>'
      );
      list.querySelectorAll('.del').forEach(span => {
        span.addEventListener('click', () => deleteSchedule(parseInt(span.dataset.ch, 10), parseInt(span.dataset.idx, 10)));
      });
    });
  }

  async function loadSchedules() {
    try {
      const r = await fetch('/api/schedules');
      const j = await r.json();
      if (j.ok) renderSchedules(j);
    } catch (_) {}
  }

  async function deleteSchedule(ch, index) {
    if (!confirm('이 스케줄을 삭제할까요?')) return;
    try {
      const r = await fetch('/api/schedules/' + ch + '/' + index, { method: 'DELETE' });
      const j = await r.json();
      if (j.ok) loadSchedules();
    } catch (e) { alert(e.message); }
  }

  function openModal(ch, index, item) {
    scheduleEdit = { channel: ch, index: index };
    modalCh.textContent = ch + 'ch';
    onTime.value = item ? item.on_time : '09:00';
    offTime.value = item ? item.off_time : '18:00';
    days.value = item && item.days ? item.days : 'daily';
    modal.classList.remove('hidden');
  }

  modalCancel.addEventListener('click', () => { modal.classList.add('hidden'); });
  modalSave.addEventListener('click', async () => {
    const ch = scheduleEdit.channel;
    const idx = scheduleEdit.index;
    const body = { on_time: onTime.value, off_time: offTime.value, days: days.value || 'daily' };
    try {
      if (idx === null) {
        const r = await fetch('/api/schedules', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ channel: ch, ...body }) });
        const j = await r.json();
        if (!j.ok) { alert(j.error || '추가 실패'); return; }
      } else {
        const r = await fetch('/api/schedules/' + ch + '/' + idx, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        const j = await r.json();
        if (!j.ok) { alert(j.error || '수정 실패'); return; }
      }
      modal.classList.add('hidden');
      loadSchedules();
    } catch (e) { alert(e.message); }
  });

  document.querySelectorAll('.add-schedule').forEach(btn => {
    btn.addEventListener('click', () => {
      const ch = parseInt(btn.dataset.ch, 10);
      const list = document.getElementById('list' + ch);
      const count = list ? list.querySelectorAll('li').length : 0;
      if (count >= 10) { alert('채널당 최대 10개까지 가능합니다.'); return; }
      openModal(ch, null, null);
    });
  });

  // 토양 센서 주간 그래프 — 지표별 7개(온·습·EC·pH·N·P·K), X·Y축 고정, X축 1시간 단위 라벨
  const MAX_POINTS = 400;
  const Y_AXIS = { temp: [0, 50], humi: [0, 100], ec: [0, 2000], ph: [0, 14], npk: [0, 200] };
  let chartTemp = null, chartHumi = null, chartEC = null, chartPH = null, chartN = null, chartP = null, chartK = null;
  const ALL_CHARTS = () => [chartTemp, chartHumi, chartEC, chartPH, chartN, chartP, chartK].filter(Boolean);

  function makeChart(canvasId, label, color, yMin, yMax) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx.getContext('2d'), {
      type: 'line',
      data: { labels: [], datasets: [{ label: label, data: [], borderColor: color, tension: 0.1, fill: false }] },
      options: {
        responsive: true,
        animation: false,
        scales: {
          x: { display: true, title: { display: true, text: '시각 (1h)' }, min: 0, max: MAX_POINTS - 1 },
          y: { display: true, min: yMin, max: yMax }
        }
      }
    });
  }

  async function refreshBadgeChart() {
    try {
      const r = await fetch('/api/badge/history?days=7&limit=3000');
      const j = await r.json();
      if (!j.ok || !j.history || !j.history.length) {
        ALL_CHARTS().forEach((c) => {
          if (c) { c.data.labels = []; c.data.datasets[0].data = []; c.update('none'); }
        });
        return;
      }
      const hist = j.history.slice(-MAX_POINTS);
      // 1시간 단위만 라벨 표시 (분이 0인 시점만)
      const labels = hist.map((d) => {
        const dt = new Date(d.t * 1000);
        const min = dt.getMinutes();
        if (min !== 0) return '';
        return dt.toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit' });
      });
      const temp = [], humi = [], ec = [], ph = [], n = [], p = [], k = [];
      hist.forEach((d) => {
        try {
          const raw = typeof d.raw === 'string' ? JSON.parse(d.raw) : d.raw;
          if (raw && typeof raw === 'object') {
            temp.push(raw.soil_temperature != null ? Number(raw.soil_temperature) : null);
            humi.push(raw.soil_humidity != null ? Number(raw.soil_humidity) : null);
            ec.push(raw.soil_EC != null ? Number(raw.soil_EC) : null);
            ph.push(raw.soil_ph != null ? Number(raw.soil_ph) : null);
            n.push(raw.soil_N != null ? Number(raw.soil_N) : null);
            p.push(raw.soil_P != null ? Number(raw.soil_P) : null);
            k.push(raw.soil_K != null ? Number(raw.soil_K) : null);
          } else {
            temp.push(null); humi.push(null); ec.push(null); ph.push(null); n.push(null); p.push(null); k.push(null);
          }
        } catch (e) {
          temp.push(null); humi.push(null); ec.push(null); ph.push(null); n.push(null); p.push(null); k.push(null);
        }
      });

      if (!chartTemp) {
        chartTemp = makeChart('chartTemp', '온도(°C)', 'rgb(255,99,71)', Y_AXIS.temp[0], Y_AXIS.temp[1]);
        chartHumi = makeChart('chartHumi', '습도(%)', 'rgb(65,105,225)', Y_AXIS.humi[0], Y_AXIS.humi[1]);
        chartEC  = makeChart('chartEC',  'EC(µS/cm)', 'rgb(34,139,34)', Y_AXIS.ec[0], Y_AXIS.ec[1]);
        chartPH  = makeChart('chartPH',  'pH', 'rgb(148,0,211)', Y_AXIS.ph[0], Y_AXIS.ph[1]);
        chartN   = makeChart('chartN',   'N', 'rgb(205,133,63)', Y_AXIS.npk[0], Y_AXIS.npk[1]);
        chartP   = makeChart('chartP',   'P', 'rgb(70,130,180)', Y_AXIS.npk[0], Y_AXIS.npk[1]);
        chartK   = makeChart('chartK',   'K', 'rgb(85,107,47)', Y_AXIS.npk[0], Y_AXIS.npk[1]);
      }
      chartTemp.data.labels = labels;
      chartTemp.data.datasets[0].data = temp;
      chartHumi.data.labels = labels;
      chartHumi.data.datasets[0].data = humi;
      chartEC.data.labels = labels;
      chartEC.data.datasets[0].data = ec;
      chartPH.data.labels = labels;
      chartPH.data.datasets[0].data = ph;
      chartN.data.labels = labels;
      chartN.data.datasets[0].data = n;
      chartP.data.labels = labels;
      chartP.data.datasets[0].data = p;
      chartK.data.labels = labels;
      chartK.data.datasets[0].data = k;
      // X축 고정 — 매 갱신 시 min/max 재설정
      ALL_CHARTS().forEach((c) => {
        if (c && c.options && c.options.scales && c.options.scales.x) {
          c.options.scales.x.min = 0;
          c.options.scales.x.max = MAX_POINTS - 1;
        }
        c.update('none');
      });
    } catch (_) {}
  }
  setInterval(refreshBadgeChart, 5000);
  refreshBadgeChart();

  fetchSerialStatus();
  loadSchedules();
  setInterval(refreshState, 3000);
})();
