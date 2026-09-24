(function () {
  "use strict";

  var ASPECT_LABELS = LOC.codebooks.aspect; // ["Food","Service","Staff","Cleanliness","Waiting Time","Order Accuracy","Value"]
  var ASPECT_COL = ["aF", "aS", "aT", "aC", "aW", "aO", "aV"];
  var ASPECT_PEERPCT_COL = ["pF", "pS", "pT", "pC", "pW", "pO", "pV"];
  var RISK_COLOR = { "Critical Risk": "var(--critical)", "High Risk": "var(--high-risk)", "Watch": "var(--watch)", "Healthy": "var(--good)" };
  var RISK_PASTEL = { "Critical Risk": "var(--critical-pastel)", "High Risk": "var(--highrisk-pastel)", "Watch": "var(--watch-pastel)", "Healthy": "var(--good-pastel)" };
  var PRIORITY_COLOR = { "Critical": "var(--critical)", "High": "var(--watch)", "Medium": "var(--accent)", "Low": "var(--text-faint)" };
  var TRAJ_ARROW = { "Deteriorating": "▼", "Stable": "→", "Improving": "▲", "Insufficient Evidence": "—" };
  var TRAJ_COLOR = { "Deteriorating": "var(--critical)", "Stable": "var(--watch)", "Improving": "var(--good)", "Insufficient Evidence": "var(--text-faint)" };
  var TRAJ_NEON = { "Deteriorating": "var(--neon-critical)", "Stable": "var(--neon-watch)", "Improving": "var(--neon-good)", "Insufficient Evidence": "var(--text-faint)" };
  var CONF_COLOR = { "Low": "var(--critical)", "Medium": "var(--watch)", "High": "var(--good)" };

  // ---------------------------------------------------------------- decode
  function un(v, scale, na) {
    if (v === (na === undefined ? -999 : na)) return null;
    return scale ? v / scale : v;
  }

  var ROWS = (function expand() {
    var cb = LOC.codebooks, n = LOC.n, out = new Array(n);
    for (var i = 0; i < n; i++) {
      var mo = un(LOC.mo[i], 10);
      var tna = LOC.tna[i];
      var aspects = {}, aspectsPeerPct = {};
      for (var a = 0; a < ASPECT_LABELS.length; a++) {
        aspects[ASPECT_LABELS[a]] = un(LOC[ASPECT_COL[a]][i], 10);
        aspectsPeerPct[ASPECT_LABELS[a]] = un(LOC[ASPECT_PEERPCT_COL[a]][i], 1);
      }
      out[i] = {
        id: LOC.id[i], name: LOC.nm[i], city: LOC.ct[i], state: LOC.st[i],
        segment: cb.segment[LOC.sg[i]], emoji: cb.segmentEmoji[LOC.sg[i]],
        lat: un(LOC.lat[i], 100), lon: un(LOC.lon[i], 100),
        stars: un(LOC.str[i], 10), reviews: LOC.rv[i],
        lhi: un(LOC.lhi[i], 10),
        risk: cb.risk[LOC.rsk[i]], priority: cb.priority[LOC.pri[i]], confidence: cb.confidence[LOC.cnf[i]],
        dataQuality: LOC.dq[i], fallback: cb.fallback[LOC.fb[i]],
        trajectory: cb.trajectory[LOC.trj[i]], trajMagnitude: un(LOC.tm[i], 100),
        pillars: { "Peer Performance": un(LOC.pp[i], 10), "Engagement": un(LOC.eg[i], 10), "Momentum": mo, "Customer Experience": un(LOC.cx[i], 10) },
        topPositive: cb.driver[LOC.tpos[i]], topNegative: cb.driver[LOC.tneg[i]],
        topNegAspect: tna >= 0 ? ASPECT_LABELS[tna] : null,
        aspects: aspects, aspectsPeerPct: aspectsPeerPct,
        peerPercentile: LOC.ppct[i], starGap: un(LOC.sgap[i], 100),
        peerTier: cb.peerTier[LOC.pt[i]], peerGroupSize: LOC.pgs[i],
        recentReviews: LOC.rr[i], priorReviews: LOC.pr[i],
        emergingIssue: (cb.emergingIssue && LOC.ei[i] >= 0) ? cb.emergingIssue[LOC.ei[i]] : null,
        opDaysWithHours: LOC.opdh[i] >= 0 ? LOC.opdh[i] : null,
        recentMeanStars: un(LOC.rms[i], 10), priorMeanStars: un(LOC.pms[i], 10),
      };
    }
    return out;
  })();

  var EVID_BY_ID = (function () {
    var m = {};
    for (var i = 0; i < EVID.bid.length; i++) {
      m[EVID.bid[i]] = { aspect: EVID.asp[i] >= 0 ? ASPECT_LABELS[EVID.asp[i]] : null, sentiment: EVID.sent[i] / 100, text: EVID.txt[i] };
    }
    return m;
  })();

  // ---------------------------------------------------------------- state
  var state = { search: "", stateFilter: "", segment: "", band: "All", aspect: "All", topRisk: false, deteriorating: false, sortCol: "lhi", sortDir: 1, page: 0 };
  var PAGE_SIZE = 25;
  var selectedId = null;

  function fmt1(x) { return x === null || x === undefined ? "–" : x.toFixed(1); }
  function ordinal(n) { var s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); }
  function fmt0(x) { return x === null || x === undefined ? "–" : Math.round(x).toString(); }
  function pct(x) { return x === null || x === undefined ? "–" : x + "%"; }

  // ---------------------------------------------------------------- filtering
  function filteredRows() {
    var q = state.search.trim().toLowerCase();
    return ROWS.filter(function (r) {
      if (q && r.name.toLowerCase().indexOf(q) === -1 && r.city.toLowerCase().indexOf(q) === -1) return false;
      if (state.stateFilter && r.state !== state.stateFilter) return false;
      if (state.segment && r.segment !== state.segment) return false;
      if (state.band !== "All" && r.risk !== state.band) return false;
      if (state.aspect !== "All" && r.topNegAspect !== state.aspect) return false;
      if (state.deteriorating && r.trajectory !== "Deteriorating") return false;
      return true;
    });
  }

  // ---------------------------------------------------------------- KPIs
  function renderKPIs(rows) {
    var n = rows.length;
    var avgLhi = n ? rows.reduce(function (s, r) { return s + r.lhi; }, 0) / n : 0;
    var avgStars = n ? rows.reduce(function (s, r) { return s + r.stars; }, 0) / n : 0;
    var totalReviews = rows.reduce(function (s, r) { return s + r.reviews; }, 0);
    var counts = { "Healthy": 0, "Watch": 0, "High Risk": 0, "Critical Risk": 0 };
    var deteriorating = 0, escalated = 0;
    rows.forEach(function (r) {
      counts[r.risk] = (counts[r.risk] || 0) + 1;
      if (r.trajectory === "Deteriorating") {
        deteriorating++;
        if (r.risk === "Healthy" || r.risk === "Watch") escalated++;
      }
    });
    var highRisk = counts["High Risk"] + counts["Critical Risk"];

    var cards = [
      { lbl: "Open Locations", val: n.toLocaleString(), foot: state.stateFilter || state.segment ? "filtered view" : META.states.length + " states · " + META.segments.length + " segments" },
      { lbl: "Average LHI", val: fmt1(avgLhi), foot: "Portfolio benchmark " + META.avgLhi, cls: "" },
      { lbl: "High / Critical Risk", val: highRisk.toLocaleString(), foot: n ? pct(Math.round(highRisk / n * 100)) + " of view" : "", cls: "accentCritical" },
      { lbl: "Watch", val: counts["Watch"].toLocaleString(), foot: n ? pct(Math.round(counts["Watch"] / n * 100)) + " of view" : "", cls: "accentWatch" },
      { lbl: "Healthy", val: counts["Healthy"].toLocaleString(), foot: n ? pct(Math.round(counts["Healthy"] / n * 100)) + " of view" : "", cls: "accentGood" },
      { lbl: "Deteriorating", val: deteriorating.toLocaleString(), foot: escalated + " currently healthy/watch — early warning", cls: "accentCritical" },
      { lbl: "Avg Rating", val: fmt1(avgStars) + "★", foot: totalReviews.toLocaleString() + " reviews in view" },
    ];
    document.getElementById("kpiGrid").innerHTML = cards.map(function (c) {
      return '<div class="kpi ' + (c.cls || "") + '"><div class="lbl">' + c.lbl + '</div><div class="val">' + c.val + '</div><div class="foot">' + c.foot + '</div></div>';
    }).join("");
  }

  // ---------------------------------------------------------------- map (Leaflet + markercluster)
  function getCss(varName) { return getComputedStyle(document.documentElement).getPropertyValue(varName).trim(); }

  var LIGHT_TILE = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
  // Esri's World_Dark_Gray_Base: free, keyless, single-server (no {s} subdomain), z/y/x tile order
  // (Esri's REST tile convention, not OSM's z/x/y) -- CARTO's dark_all basemap now requires a
  // registered API key for anonymous use, confirmed by an "API KEY REQUIRED" watermark on the tiles.
  var DARK_TILE = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}';
  var map = null, markerClusterGroup = null, initialBounds = null, tileLayer = null;

  function isDarkTheme() {
    var t = document.documentElement.getAttribute("data-theme");
    if (t === "dark") return true;
    if (t === "light") return false;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function resolveRiskColors() {
    return {
      "Healthy": getCss("--good"), "Watch": getCss("--watch"),
      "High Risk": getCss("--high-risk"), "Critical Risk": getCss("--critical"),
    };
  }

  // Colors are re-resolved fresh on every renderMap() call (theme can change between calls) and
  // stashed here, rather than captured once at map-init time -- iconCreateFunction is set once on
  // the cluster group, so it must read live colors on each invocation, not a stale init-time snapshot.
  var currentRiskColors = null;
  function clusterIconFn(cluster) {
    var colors = currentRiskColors;
    var kids = cluster.getAllChildMarkers();
    var worst = kids.some(function (k) { return k.riskBand === "Critical Risk"; }) ? colors["Critical Risk"]
      : kids.some(function (k) { return k.riskBand === "High Risk"; }) ? colors["High Risk"]
      : kids.some(function (k) { return k.riskBand === "Watch"; }) ? colors["Watch"]
      : colors["Healthy"];
    var n = kids.length, size = n < 10 ? 30 : n < 100 ? 36 : n < 1000 ? 44 : 52;
    return L.divIcon({
      html: '<div class="clusterBubble" style="background:' + worst + '">' + n.toLocaleString() + '</div>',
      className: "clusterIconWrap", iconSize: [size, size],
    });
  }

  function makeTileLayer() {
    var dark = isDarkTheme();
    return L.tileLayer(dark ? DARK_TILE : LIGHT_TILE, {
      maxZoom: dark ? 16 : 19,
      subdomains: dark ? "" : "abc",
      attribution: dark
        ? "Tiles &copy; Esri"
        : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    });
  }

  function ensureMapInit() {
    if (map) return;
    map = L.map("mapDiv", { preferCanvas: true, zoomControl: true, minZoom: 3 });
    var latR = META.latRange, lonR = META.lonRange;
    initialBounds = L.latLngBounds([latR[0], lonR[0]], [latR[1], lonR[1]]);
    map.fitBounds(initialBounds, { padding: [20, 20] });

    tileLayer = makeTileLayer().addTo(map);

    markerClusterGroup = L.markerClusterGroup({
      chunkedLoading: true, chunkInterval: 200, chunkDelay: 30,
      spiderfyOnMaxZoom: true, disableClusteringAtZoom: 16,
      maxClusterRadius: 60, removeOutsideVisibleBounds: true,
      iconCreateFunction: clusterIconFn,
    });
    map.addLayer(markerClusterGroup);
  }

  function renderMap(rows) {
    ensureMapInit();
    markerClusterGroup.clearLayers();
    var colors = resolveRiskColors();
    currentRiskColors = colors;
    var markers = rows.map(function (r) {
      var m = L.circleMarker([r.lat, r.lon], {
        radius: r.risk === "Healthy" ? 4 : 5,
        weight: 1, color: colors[r.risk], fillColor: colors[r.risk],
        fillOpacity: r.risk === "Healthy" ? 0.45 : 0.85,
      });
      m.riskBand = r.risk;
      m.bindTooltip(
        "<b>" + escapeHtml(r.name) + "</b><br>" + escapeHtml(r.city) + ", " + r.state + " · LHI " + fmt1(r.lhi) + " · " + r.risk,
        { sticky: true, direction: "top", className: "mapLeafletTip" }
      );
      m.on("click", function () { openDrawer(r.id); });
      return m;
    });
    markerClusterGroup.addLayers(markers);
  }

  document.getElementById("resetMapBtn").addEventListener("click", function () {
    if (map && initialBounds) map.fitBounds(initialBounds, { padding: [20, 20] });
  });

  // ---------------------------------------------------------------- histogram
  var RISK_BANDS_ORDER = ["Healthy", "Watch", "High Risk", "Critical Risk"];
  function renderHist(rows) {
    var edges = META.histogram.edges;
    var nBins = edges.length - 1;
    // Per-bin composition by ACTUAL risk band (not inferred from bin midpoint) -- a bin can
    // legitimately straddle a RISK_BAND_EDGES threshold (bins are fixed 4-pt slices; the
    // thresholds sit at 25/40/60, so e.g. the 24-28 bin holds both Critical and High Risk rows).
    var bins = [];
    for (var i = 0; i < nBins; i++) bins.push({ Healthy: 0, Watch: 0, "High Risk": 0, "Critical Risk": 0, total: 0 });
    rows.forEach(function (r) {
      var idx = Math.min(nBins - 1, Math.max(0, Math.floor(r.lhi / 4)));
      bins[idx][r.risk] = (bins[idx][r.risk] || 0) + 1;
      bins[idx].total++;
    });
    var max = Math.max.apply(null, bins.map(function (b) { return b.total; }).concat([1]));
    var pastelVar = { "Healthy": "--good-pastel", "Watch": "--watch-pastel", "High Risk": "--highrisk-pastel", "Critical Risk": "--critical-pastel" };
    var solidVar = { "Healthy": "--good", "Watch": "--watch", "High Risk": "--high-risk", "Critical Risk": "--critical" };
    var barsHtml = bins.map(function (b, i) {
      var hPct = Math.max(2, b.total / max * 100);
      var tipRows = RISK_BANDS_ORDER.map(function (band) {
        var pct = b.total ? Math.round(b[band] / b.total * 100) : 0;
        if (!b[band]) return "";
        return '<div class="tipRow"><span class="tipDot" style="background:var(' + solidVar[band] + ')"></span>' +
          '<span>' + band + '</span><b>' + pct + '%</b></div>';
      }).join("");
      // Stack all four bands bottom-up (Healthy at base, Critical Risk at top) proportional to
      // their share of this bin -- the bar's overall height/silhouette (hPct, driven by total
      // count) stays the dominant visual signal; color composition rides along inside it.
      var segs = b.total ? RISK_BANDS_ORDER.map(function (band) {
        if (!b[band]) return "";
        var segPct = b[band] / b.total * 100;
        return '<span class="histSeg" style="flex-basis:' + segPct + '%;background:var(' + pastelVar[band] + ')"></span>';
      }).join("") : "";
      return '<div class="histBar" style="height:' + hPct + '%">' + segs +
        '<div class="histBarTip"><b>LHI ' + edges[i] + '–' + edges[i + 1] + '</b><br>' + b.total.toLocaleString() + ' locations' +
        (tipRows ? '<div style="margin-top:6px">' + tipRows + '</div>' : '') + '</div>' +
        '</div>';
    }).join("");
    var medianLine = (META.medianLhi !== undefined && META.medianLhi !== null) ?
      '<div class="histMedianLine" style="left:' + META.medianLhi + '%" title="Portfolio median LHI ' + META.medianLhi + '"></div>' : "";
    document.getElementById("histBars").innerHTML = barsHtml + medianLine;
  }

  // ---------------------------------------------------------------- segment list
  function renderSegList(rows) {
    var bySeg = {};
    rows.forEach(function (r) {
      var s = bySeg[r.segment] || (bySeg[r.segment] = { Healthy: 0, Watch: 0, "High Risk": 0, "Critical Risk": 0, total: 0 });
      s[r.risk] = (s[r.risk] || 0) + 1; s.total++;
    });
    var entries = Object.keys(bySeg).map(function (k) { return [k, bySeg[k]]; }).sort(function (a, b) { return b[1].total - a[1].total; });
    document.getElementById("segList").innerHTML = entries.map(function (e) {
      var seg = e[0], d = e[1];
      var emoji = LOC.codebooks.segmentEmoji[LOC.codebooks.segment.indexOf(seg)] || "";
      var stack = RISK_BANDS_ORDER.map(function (band) {
        var pct = d.total ? d[band] / d.total * 100 : 0;
        if (pct <= 0) return "";
        return '<span style="width:' + pct + '%;background:' + RISK_PASTEL[band] + '" title="' + band + ': ' +
          d[band].toLocaleString() + ' (' + Math.round(pct) + '%)"></span>';
      }).join("");
      return '<div class="segRow"><span class="segName">' + emoji + " " + seg + '</span>' +
        '<span class="segBarTrack">' + stack + '</span>' +
        '<span class="segCount">' + d.total.toLocaleString() + '</span></div>';
    }).join("") || '<div class="emptyState">No locations match the current filters</div>';
  }

  // ---------------------------------------------------------------- aspect panel
  function renderAspects(rows) {
    var chipsEl = document.getElementById("aspectChips");
    var counts = { "All": rows.length };
    ASPECT_LABELS.forEach(function (a) { counts[a] = 0; });
    rows.forEach(function (r) { if (r.topNegAspect) counts[r.topNegAspect]++; });
    var chips = ["All"].concat(ASPECT_LABELS);
    chipsEl.innerHTML = chips.map(function (a) {
      return '<button class="chip' + (state.aspect === a ? " active" : "") + '" data-aspect="' + a + '">' + a + ' <span class="n">' + counts[a].toLocaleString() + '</span></button>';
    }).join("");
    chipsEl.querySelectorAll(".chip").forEach(function (el) {
      el.addEventListener("click", function () { state.aspect = el.getAttribute("data-aspect"); state.page = 0; renderAll(); });
    });

    var gridEl = document.getElementById("aspectGrid");
    var stats = ASPECT_LABELS.map(function (a) {
      var withAspect = rows.filter(function (r) { return r.aspects[a] !== null; });
      var mean = withAspect.length ? withAspect.reduce(function (s, r) { return s + r.aspects[a]; }, 0) / withAspect.length : null;
      var primary = rows.filter(function (r) { return r.topNegAspect === a; });
      var highRiskShare = primary.length ? Math.round(primary.filter(function (r) { return r.risk === "High Risk" || r.risk === "Critical Risk"; }).length / primary.length * 100) : 0;
      return { a: a, mean: mean, count: primary.length, highRiskShare: highRiskShare };
    });
    var withMean = stats.filter(function (s) { return s.mean !== null; });
    var benchmark = withMean.length ? withMean.reduce(function (s, x) { return s + x.mean; }, 0) / withMean.length : null;
    var weakestMean = withMean.length ? Math.min.apply(null, withMean.map(function (s) { return s.mean; })) : null;
    // Ranked ascending -- weakest (highest-risk) aspect first, matching the "which of N is worst"
    // reading this panel is used for; aspects with no evidence in the current filter sink to the end.
    var ranked = stats.slice().sort(function (x, y) {
      var xv = x.mean === null ? Infinity : x.mean, yv = y.mean === null ? Infinity : y.mean;
      return xv - yv;
    });
    gridEl.innerHTML = ranked.map(function (s) {
      var isWeakest = s.mean !== null && s.mean === weakestMean;
      var refTick = benchmark !== null ? '<span class="arRef" style="left:' + benchmark + '%" title="Portfolio mean ' + fmt1(benchmark) + '"></span>' : "";
      return '<div class="aspectRankRow' + (state.aspect === s.a ? " active" : "") + (isWeakest ? " weakest" : "") + '" data-aspect="' + s.a + '">' +
        '<span class="arName">' + s.a + '</span>' +
        '<span class="arTrack"><span class="arFill" style="width:' + (s.mean === null ? 0 : s.mean) + '%"></span>' + refTick + '</span>' +
        '<span class="arScore">' + (s.mean === null ? "–" : fmt1(s.mean)) + '</span>' +
        '<span class="arFoot">' + s.count.toLocaleString() + ' · ' + s.highRiskShare + '% high risk</span></div>';
    }).join("");
    gridEl.querySelectorAll(".aspectRankRow").forEach(function (el) {
      el.addEventListener("click", function () {
        var a = el.getAttribute("data-aspect");
        state.aspect = state.aspect === a ? "All" : a; state.page = 0; renderAll();
      });
    });
  }

  // ---------------------------------------------------------------- table
  var COLS = [
    { key: "name", label: "Location", sort: false },
    { key: "city", label: "City", sort: false },
    { key: "segment", label: "Segment", sort: false },
    { key: "stars", label: "Stars", sort: true, num: true },
    { key: "reviews", label: "Reviews", sort: true, num: true },
    { key: "lhi", label: "LHI", sort: true, num: true },
    { key: "trajectory", label: "12M Trend", sort: true },
    { key: "priority", label: "Priority", sort: true },
    { key: "topNegative", label: "Risk Driver", sort: false },
  ];

  function renderTableHead() {
    document.getElementById("tableHead").innerHTML = COLS.map(function (c) {
      var sorted = state.sortCol === c.key;
      return '<th data-key="' + c.key + '" class="' + (sorted ? "sorted" : "") + '">' + c.label + (sorted ? (state.sortDir === 1 ? " ↑" : " ↓") : "") + '</th>';
    }).join("");
    document.querySelectorAll("#tableHead th").forEach(function (th) {
      th.addEventListener("click", function () {
        var key = th.getAttribute("data-key");
        var col = COLS.filter(function (c) { return c.key === key; })[0];
        if (!col.sort) return;
        if (state.sortCol === key) state.sortDir *= -1; else { state.sortCol = key; state.sortDir = 1; }
        renderAll();
      });
    });
  }

  function riskBadgeHtml(risk) {
    var color = RISK_COLOR[risk];
    return '<span class="badge" style="background:color-mix(in srgb, ' + color + ' 16%, transparent); color:' + color + '">' + risk + '</span>';
  }
  function priorityBadgeHtml(p) {
    var color = PRIORITY_COLOR[p];
    return '<span class="badge" style="background:color-mix(in srgb, ' + color + ' 16%, transparent); color:' + color + '">' + p + '</span>';
  }

  // Compact per-row sparkline: same 2-point prior-vs-recent evidence used in the drawer's
  // trend/median chart, never a fabricated multi-point curve. Insufficient-evidence rows get a
  // flat, muted placeholder line -- visibly "no data," not a fake trend. Neon glow + gradient
  // area fill styled after a stocks-app trend widget; the median line is drawn in the same neon
  // color as the trend (dashed, lower opacity), not a separate neutral tone, matching that
  // reference exactly.
  var sparkUid = 0;
  function sparklineHtml(r) {
    var W = 96, H = 30, padX = 6, padY = 5;
    var neon = TRAJ_NEON[r.trajectory] || "var(--text-faint)";
    var uid = "spark" + (sparkUid++);
    var defs = '<defs>' +
      '<filter id="g' + uid + '" x="-60%" y="-60%" width="220%" height="220%">' +
        '<feDropShadow dx="0" dy="0" stdDeviation="0.9" flood-color="' + neon + '" flood-opacity="0.9"/>' +
        '<feDropShadow dx="0" dy="0" stdDeviation="2.4" flood-color="' + neon + '" flood-opacity="0.6"/>' +
      '</filter>' +
      '<linearGradient id="f' + uid + '" x1="0" y1="0" x2="0" y2="1">' +
        '<stop offset="0%" stop-color="' + neon + '" stop-opacity="0.38"/>' +
        '<stop offset="100%" stop-color="' + neon + '" stop-opacity="0"/>' +
      '</linearGradient>' +
    '</defs>';
    if (r.recentMeanStars === null || r.priorMeanStars === null) {
      var yFlat = H / 2;
      return '<div class="sparkWrap" title="Insufficient Evidence — not enough review history in both windows">' +
        '<div class="sparkDelta" style="color:var(--text-faint)">—</div>' +
        '<svg class="sparkSvg" viewBox="0 0 ' + W + ' ' + H + '">' +
        '<line x1="' + padX + '" y1="' + yFlat + '" x2="' + (W - padX) + '" y2="' + yFlat +
        '" stroke="var(--text-faint)" stroke-width="2" stroke-linecap="round" opacity="0.4"/></svg></div>';
    }
    var domainLo = 1, domainHi = 5;
    function yOf(v) { return H - padY - (v - domainLo) / (domainHi - domainLo) * (H - padY * 2); }
    var x1 = padX, x2 = W - padX;
    var y1 = yOf(r.priorMeanStars), y2 = yOf(r.recentMeanStars);
    var yMid = (y1 + y2) / 2 - Math.abs(y1 - y2) * 0.15;
    var medianStars = META.medianStars;
    var medianLine = (medianStars !== null && medianStars !== undefined) ?
      '<line x1="' + padX + '" y1="' + yOf(medianStars) + '" x2="' + (W - padX) + '" y2="' + yOf(medianStars) +
      '" stroke="' + neon + '" stroke-width="1" stroke-dasharray="2,2" opacity="0.55"/>' : "";
    var delta = r.trajMagnitude !== null ? (r.trajMagnitude > 0 ? "+" : "") + r.trajMagnitude.toFixed(2) + "★" : "";
    return '<div class="sparkWrap" title="' + fmt1(r.priorMeanStars) + '★ prior → ' + fmt1(r.recentMeanStars) + '★ recent · ' + r.trajectory + '">' +
      '<div class="sparkDelta" style="color:' + neon + '">' + TRAJ_ARROW[r.trajectory] + ' ' + delta + '</div>' +
      '<svg class="sparkSvg" viewBox="0 0 ' + W + ' ' + H + '">' + defs +
      medianLine +
      '<path d="M ' + x1 + ' ' + y1 + ' Q ' + ((x1 + x2) / 2) + ' ' + yMid + ' ' + x2 + ' ' + y2 + ' L ' + x2 + ' ' + H + ' L ' + x1 + ' ' + H + ' Z"' +
      ' fill="url(#f' + uid + ')" stroke="none"/>' +
      '<path d="M ' + x1 + ' ' + y1 + ' Q ' + ((x1 + x2) / 2) + ' ' + yMid + ' ' + x2 + ' ' + y2 +
      '" fill="none" stroke="' + neon + '" stroke-width="2" stroke-linecap="round" filter="url(#g' + uid + ')"/>' +
      '<circle cx="' + x2 + '" cy="' + y2 + '" r="2.2" fill="' + neon + '"/>' +
      '</svg></div>';
  }

  function renderTable(rows) {
    var sorted = rows.slice();
    if (state.sortCol) {
      var col = COLS.filter(function (c) { return c.key === state.sortCol; })[0];
      sorted.sort(function (a, b) {
        var av = a[state.sortCol], bv = b[state.sortCol];
        if (col.num) return (av - bv) * state.sortDir;
        return String(av).localeCompare(String(bv)) * state.sortDir;
      });
    }
    var display = state.topRisk ? sorted.slice().sort(function (a, b) { return a.lhi - b.lhi; }).slice(0, 100) : sorted;

    var totalPages = Math.max(1, Math.ceil(display.length / PAGE_SIZE));
    state.page = Math.min(state.page, totalPages - 1);
    var pageRows = display.slice(state.page * PAGE_SIZE, (state.page + 1) * PAGE_SIZE);

    document.getElementById("tableBody").innerHTML = pageRows.length ? pageRows.map(function (r) {
      var lhiColor = RISK_COLOR[r.risk];
      return '<tr data-id="' + r.id + '">' +
        '<td><div class="locName">' + r.emoji + ' ' + escapeHtml(r.name) + '</div></td>' +
        '<td class="locCity">' + escapeHtml(r.city) + ', ' + r.state + '</td>' +
        '<td>' + r.segment + '</td>' +
        '<td class="numCell">' + fmt1(r.stars) + '★</td>' +
        '<td class="numCell">' + r.reviews.toLocaleString() + '</td>' +
        '<td class="numCell"><div class="lhiBar"><span>' + fmt1(r.lhi) + '</span><span class="lhiBarTrack" title="' + r.risk + ' · ' + fmt1(r.lhi) + '/100"><span class="lhiBarFill" style="width:' + Math.max(r.lhi, 2) + '%;background:' + lhiColor + '"></span></span></div></td>' +
        '<td>' + sparklineHtml(r) + '</td>' +
        '<td>' + priorityBadgeHtml(r.priority) + '</td>' +
        '<td>' + (r.topNegative === "PEER" ? "Peer Performance" : r.topNegative === "CX" ? "Customer Experience" : r.topNegative.charAt(0) + r.topNegative.slice(1).toLowerCase()) + '</td>' +
        '</tr>';
    }).join("") : '<tr><td colspan="9"><div class="emptyState">No locations match the current filters</div></td></tr>';

    document.querySelectorAll("#tableBody tr[data-id]").forEach(function (tr) {
      tr.addEventListener("click", function () { openDrawer(tr.getAttribute("data-id")); });
    });

    document.getElementById("pagerInfo").textContent = display.length ?
      ("Showing " + (state.page * PAGE_SIZE + 1) + "–" + Math.min(display.length, (state.page + 1) * PAGE_SIZE) + " of " + display.length.toLocaleString() +
        (state.topRisk ? " (top 100 by risk)" : "")) : "No results";
    document.getElementById("prevPage").disabled = state.page === 0;
    document.getElementById("nextPage").disabled = state.page >= totalPages - 1;
    document.getElementById("tableSub").textContent = state.topRisk ? "Top 100 open locations by LHI, ascending" :
      "Sorted by " + COLS.filter(function (c) { return c.key === state.sortCol; })[0].label + (state.sortDir === 1 ? " (ascending)" : " (descending)") + " · click a row for full diagnostic detail";
  }

  function escapeHtml(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  document.getElementById("prevPage").addEventListener("click", function () { state.page = Math.max(0, state.page - 1); renderTable(filteredRows()); });
  document.getElementById("nextPage").addEventListener("click", function () { state.page++; renderTable(filteredRows()); });

  // ---------------------------------------------------------------- drawer
  var drawer = document.getElementById("drawer"), scrim = document.getElementById("scrim");

  function trajInterpretation(r) {
    var healthWord = r.risk === "Healthy" ? "Healthy" : r.risk === "Watch" ? "Below target" : "Unhealthy";
    if (r.trajectory === "Insufficient Evidence") return healthWord + " — not enough recent review history (min. 5 reviews in both the trailing and prior 12-month windows) to evidence a trend either way.";
    if (r.trajectory === "Improving") return healthWord + " and recovering — recent sentiment/rating is statistically higher than the prior 12 months.";
    if (r.trajectory === "Stable") return healthWord + " and holding steady — no statistically significant shift recent vs. prior 12 months.";
    if (r.risk === "Healthy") return "Currently healthy, but this is a deterioration warning — a statistically real decline is underway even though the score is still above the peer median.";
    return healthWord + " and deteriorating — this compounds the existing risk and is treated as higher priority than the score alone would suggest.";
  }

  function lhiFillBarHtml(r) {
    var color = RISK_COLOR[r.risk] || "var(--text-faint)";
    var h = Math.max(2, Math.round(r.lhi));
    return '<div class="lhiFillTrack" title="LHI fill, colored by risk band"><div class="lhiFillBar" style="height:' + h + '%;background:' + color + '"></div></div>';
  }

  function trendMedianHtml(r) {
    // Gate: never draw a 2-point line from missing data (RECENT_MEAN_STARS/PRIOR_MEAN_STARS are
    // only populated when the same min-review-per-window gate that sets r.trajectory is satisfied).
    if (r.recentMeanStars === null || r.priorMeanStars === null) {
      return '<div class="trendMedianWrap"><p style="color:var(--text-faint);font-size:11.5px;margin:6px 0 0">' +
        'Not enough review history in both windows to plot a trend line (same evidence bar as Trajectory above).</p></div>';
    }
    var W = 400, H = 70, padX = 34, padY = 12;
    var domainLo = 1, domainHi = 5;
    function yOf(v) { return H - padY - (v - domainLo) / (domainHi - domainLo) * (H - padY * 2); }
    var xPrior = padX, xRecent = W - padX;
    var yPrior = yOf(r.priorMeanStars), yRecent = yOf(r.recentMeanStars);
    var medianStars = META.medianStars;
    var yMedian = medianStars !== null && medianStars !== undefined ? yOf(medianStars) : null;
    var lineColor = TRAJ_COLOR[r.trajectory] || "var(--watch)";
    var medianLine = yMedian !== null ?
      '<line x1="' + padX + '" y1="' + yMedian + '" x2="' + (W - padX) + '" y2="' + yMedian +
      '" stroke="var(--text-faint)" stroke-width="1" stroke-dasharray="3,3"/>' +
      '<text x="' + (W - padX) + '" y="' + (yMedian - 4) + '" text-anchor="end" font-size="9" fill="var(--text-faint)">portfolio median ' + medianStars.toFixed(1) + '★</text>'
      : "";
    return '<div class="trendMedianWrap">' +
      '<svg class="trendMedianSvg" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none">' +
        medianLine +
        '<line x1="' + xPrior + '" y1="' + yPrior + '" x2="' + xRecent + '" y2="' + yRecent + '" stroke="' + lineColor + '" stroke-width="2.5"/>' +
        '<circle cx="' + xPrior + '" cy="' + yPrior + '" r="4" fill="' + lineColor + '"/>' +
        '<circle cx="' + xRecent + '" cy="' + yRecent + '" r="4" fill="' + lineColor + '"/>' +
        '<text x="' + xPrior + '" y="' + (yPrior + (yPrior > H / 2 ? -8 : 16)) + '" text-anchor="middle" font-size="10" font-weight="600" fill="' + lineColor + '">' + r.priorMeanStars.toFixed(2) + '★</text>' +
        '<text x="' + xRecent + '" y="' + (yRecent + (yRecent > H / 2 ? -8 : 16)) + '" text-anchor="middle" font-size="10" font-weight="600" fill="' + lineColor + '">' + r.recentMeanStars.toFixed(2) + '★</text>' +
      '</svg>' +
      '<div class="trendMedianLabel"><span>Prior 12mo</span><span>Recent 12mo</span></div>' +
    '</div>';
  }

  function openDrawer(id) {
    var r = ROWS.filter(function (x) { return x.id === id; })[0];
    if (!r) return;
    selectedId = id;
    var ev = EVID_BY_ID[id];

    var pillarRows = Object.keys(r.pillars).map(function (k) {
      var v = r.pillars[k];
      var w = META.lhi3Weights ? META.lhi3Weights[k] : null;
      var contrib = v !== null && w !== null ? v * w : null;
      var label = v === null ? "n/a" : fmt1(v) + (contrib !== null ? " → " + contrib.toFixed(1) + "pt" : "");
      return '<div class="contribRow"><span class="cName">' + k + (w !== null ? ' <span style="opacity:.6">(' + Math.round(w * 100) + '% wt)</span>' : '') + '</span><span class="cTrack"><span class="cFill" style="width:' + (v === null ? 0 : v) + '%"></span></span><span class="cVal" style="width:auto;min-width:70px">' + label + '</span></div>';
    }).join("");

    // Ranked ascending by peer percentile -- weakest-vs-peers aspect first. Bar axis is the
    // 0-100th peer PERCENTILE (r.aspectsPeerPct), a distinct scale from the portfolio panel's
    // 0-100 absolute-sentiment axis; the absolute score stays available in the hover title.
    var aspectMini = Object.keys(r.aspects).map(function (k) {
      return { k: k, v: r.aspects[k], pp: r.aspectsPeerPct[k], weak: k === r.topNegAspect };
    }).sort(function (x, y) {
      var xv = x.pp === null ? 101 : x.pp, yv = y.pp === null ? 101 : y.pp;
      return xv - yv;
    }).map(function (it) {
      return '<div class="aspectMini' + (it.weak ? " weakest" : "") + '" title="Absolute sentiment: ' + fmt1(it.v) + ' · Peer percentile is what determines the weakest-aspect flag">' +
        '<span class="amName">' + it.k + (it.weak ? " ⚠" : "") + '</span>' +
        '<span class="amTrack"><span class="amFill" style="width:' + (it.pp === null ? 0 : it.pp) + '%"></span><span class="amRef"></span></span>' +
        '<span class="amVal">' + (it.pp === null ? "–" : ordinal(Math.round(it.pp)) + " pct") + '</span></div>';
    }).join("");

    var evidenceHtml = ev ? '<div class="evidenceCard"><div class="eTop"><span>' + ev.aspect + '</span><span>sentiment ' + ev.sentiment.toFixed(2) + '</span></div><p>“' + escapeHtml(ev.text) + '…”</p></div>' :
      '<p style="color:var(--text-dim);font-size:12.5px">No representative negative-review snippet retained for this location (weakest aspect had too little evidence, or this location is not in the flagged Watch/Risk population).</p>';

    var focusAspect = r.topNegAspect || (r.topNegative === "PEER" ? "peer positioning" : r.topNegative.toLowerCase());
    var focusText = "Investigate " + focusAspect + " — it is this location's weakest pillar relative to peers" +
      (r.trajectory === "Deteriorating" ? ", and the location is on a statistically-evidenced declining trend, which raises urgency." : ". Trend evidence does not currently show active deterioration.") +
      (r.confidence === "Low" ? " Confidence in this read is Low (thin review history) — verify on the ground before acting." : "");

    drawer.innerHTML =
      '<div class="drawerHead">' +
        '<div class="topRow">' + riskBadgeHtml(r.risk) + '<button class="closeBtn" id="drawerClose">✕</button></div>' +
        '<h3>' + escapeHtml(r.name) + '</h3>' +
        '<div class="meta">' + escapeHtml(r.city) + ', ' + r.state + ' · ' + r.emoji + ' ' + r.segment + ' · ' + fmt1(r.stars) + '★ · ' + r.reviews.toLocaleString() + ' reviews</div>' +
      '</div>' +
      '<div class="drawerBody">' +

        '<div class="dSection"><h4>Current Health</h4>' +
          '<div class="lhiGaugeWrap">' + lhiFillBarHtml(r) + '<div class="lhiGaugeNum">' + fmt1(r.lhi) + '</div>' +
            '<div class="lhiGaugeBar"><div class="gaugeTrack"><div class="gaugeMark" style="left:' + r.lhi + '%"></div></div>' +
            '<div class="gaugeAvgLabel">Portfolio avg ' + META.avgLhi + ' · ' + (META.lhiVersionLabel || "Hybrid") + ' (' + (META.lhiVersion || "").replace("_", "-") + ')</div></div></div>' +
          trendMedianHtml(r) +
        '</div>' +

        '<div class="dSection"><h4>Trajectory</h4>' +
          '<div class="trajPanel" style="border-color:' + TRAJ_COLOR[r.trajectory] + '33">' +
            '<div class="trajArrow" style="color:' + TRAJ_NEON[r.trajectory] + '">' + TRAJ_ARROW[r.trajectory] + '</div>' +
            '<div class="trajText"><b style="color:' + TRAJ_COLOR[r.trajectory] + '">' + r.trajectory + (r.trajMagnitude !== null ? " · " + (r.trajMagnitude > 0 ? "+" : "") + r.trajMagnitude.toFixed(2) + "★ vs prior 12mo" : "") + '</b>' +
            '<span>' + trajInterpretation(r) + '</span></div>' +
          '</div>' +
          '<div class="priorityRow">' + priorityBadgeHtml(r.priority) + '<span class="badge" style="background:color-mix(in srgb, ' + CONF_COLOR[r.confidence] + ' 16%, transparent); color:' + CONF_COLOR[r.confidence] + '">' + r.confidence + ' confidence</span>' +
          '<span class="badge" style="background:var(--surface-2); color:var(--text-dim)">' + r.recentReviews + ' recent / ' + r.priorReviews + ' prior reviews</span>' +
          (r.emergingIssue ? '<span class="badge" style="background:color-mix(in srgb, var(--critical) 16%, transparent); color:var(--critical)">⚠ Emerging issue: ' + escapeHtml(r.emergingIssue) + '</span>' : '') +
          '</div>' +
        '</div>' +

        '<div class="dSection"><h4>Pillar Scores &amp; Weighted Contribution</h4><div class="contribList">' + pillarRows + '</div></div>' +

        '<div class="dSection"><h4>Peer &amp; Data Context</h4><div class="statGrid">' +
          '<div class="stat"><div class="k">Peer Percentile</div><div class="v">' + (r.peerPercentile === null ? "–" : ordinal(r.peerPercentile)) + '</div></div>' +
          '<div class="stat"><div class="k">Star Gap vs Peers</div><div class="v">' + (r.starGap === null ? "–" : (r.starGap > 0 ? "+" : "") + r.starGap.toFixed(2)) + '</div></div>' +
          '<div class="stat"><div class="k">Peer Tier</div><div class="v" style="font-size:12px">' + r.peerTier.replace(/_/g, " ").replace("TIER ", "T") + '</div></div>' +
          '<div class="stat"><div class="k">Peers in Group</div><div class="v">' + (r.peerGroupSize === null ? "–" : r.peerGroupSize) + '</div></div>' +
          '<div class="stat"><div class="k">Data Quality</div><div class="v">' + r.dataQuality + '/100</div></div>' +
          '<div class="stat"><div class="k">Fallback Level</div><div class="v" style="font-size:12px">' + r.fallback.replace(/_/g, " ").replace(/^\d /, "") + '</div></div>' +
          '<div class="stat" title="Context only — not scored into LHI. See footnote."><div class="k">Operational Profile</div><div class="v">' + (r.opDaysWithHours === null ? "–" : r.opDaysWithHours + "/7 days listed") + '</div></div>' +
        '</div></div>' +

        '<div class="dSection"><h4>Aspect Sentiment vs. Peers (ABSA)</h4>' +
          '<p class="cardSub" style="margin-top:-4px">Bar length = percentile vs. peers (0–100th) · dashed line = peer median</p>' +
          '<div class="aspectMiniGrid">' + aspectMini + '</div></div>' +

        '<div class="dSection"><h4>Customer Voice — Review Evidence</h4>' + evidenceHtml + '</div>' +

        '<div class="dSection"><h4>Diagnosis</h4>' +
          '<div class="focusBox">' + focusText + '</div>' +
          '<div class="diagChain"><span>LHI ' + fmt1(r.lhi) + '</span>→<span>' + (r.topNegative === "PEER" ? "Peer Performance" : r.topNegative === "CX" ? "Customer Experience" : r.topNegative.charAt(0) + r.topNegative.slice(1).toLowerCase()) + ' weakest</span>→<span>ABSA: ' + (r.topNegAspect || "n/a") + '</span>→<span>' + (ev ? "evidence above" : "no snippet retained") + '</span></div>' +
        '</div>' +

      '</div>';

    document.getElementById("drawerClose").addEventListener("click", closeDrawer);
    drawer.classList.add("open"); scrim.classList.add("open");
  }
  function closeDrawer() { drawer.classList.remove("open"); scrim.classList.remove("open"); selectedId = null; }
  scrim.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrawer(); });

  // ---------------------------------------------------------------- filter controls
  var searchDebounce;
  document.getElementById("searchInput").addEventListener("input", function (e) {
    var v = e.target.value;
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(function () { state.search = v; state.page = 0; renderAll(); }, 130);
  });
  document.getElementById("stateSelect").addEventListener("change", function (e) { state.stateFilter = e.target.value; state.page = 0; renderAll(); });
  document.getElementById("segmentSelect").addEventListener("change", function (e) { state.segment = e.target.value; state.page = 0; renderAll(); });
  document.getElementById("topRiskBtn").addEventListener("click", function (e) {
    state.topRisk = !state.topRisk; state.page = 0;
    e.currentTarget.classList.toggle("active", state.topRisk);
    e.currentTarget.classList.add("acked"); // first click acknowledges the alert permanently -- blink never resumes
    renderTable(filteredRows());
  });
  document.getElementById("deteriorationBtn").addEventListener("click", function (e) {
    state.deteriorating = !state.deteriorating; state.page = 0;
    e.currentTarget.classList.toggle("active", state.deteriorating);
    e.currentTarget.classList.add("acked");
    renderAll();
  });

  function initSelects() {
    var stateSel = document.getElementById("stateSelect");
    META.states.forEach(function (s) { stateSel.innerHTML += '<option value="' + s + '">' + s + '</option>'; });
    var segSel = document.getElementById("segmentSelect");
    META.segments.forEach(function (s) { segSel.innerHTML += '<option value="' + s + '">' + s + '</option>'; });

    var bands = ["All", "Healthy", "Watch", "High Risk", "Critical Risk"];
    document.getElementById("bandPills").innerHTML = bands.map(function (b) {
      var c = RISK_COLOR[b];
      return '<button class="bandPill' + (state.band === b ? " active" : "") + '" data-band="' + b + '"' +
        (c ? ' style="--pulse-color:' + c + '"' : '') + '>' +
        (c ? '<i class="dot" style="background:' + c + '"></i>' : '') + b + '</button>';
    }).join("");
    document.querySelectorAll(".bandPill").forEach(function (el) {
      el.addEventListener("click", function () {
        state.band = el.getAttribute("data-band"); state.page = 0;
        document.querySelectorAll(".bandPill").forEach(function (x) { x.classList.remove("active"); });
        el.classList.add("active");
        renderAll();
      });
    });
  }

  // ---------------------------------------------------------------- theme
  document.getElementById("themeToggle").addEventListener("click", function (e) {
    var btn = e.target.closest("button"); if (!btn) return;
    var t = btn.getAttribute("data-theme");
    if (t === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", t);
    document.querySelectorAll("#themeToggle button").forEach(function (b) { b.classList.toggle("active", b === btn); });
    if (map && tileLayer) {
      map.removeLayer(tileLayer);
      tileLayer = makeTileLayer().addTo(map);
    }
    renderAll();
  });

  // ---------------------------------------------------------------- main render
  function renderAll() {
    var rows = filteredRows();
    document.getElementById("filterCount").innerHTML = rows.length.toLocaleString() + " of " + ROWS.length.toLocaleString() + " open locations";
    renderKPIs(rows);
    renderMap(rows);
    renderHist(rows);
    renderSegList(rows);
    renderAspects(rows);
    renderTable(rows);
  }

  initSelects();
  renderTableHead();
  renderAll();
  window.addEventListener("resize", function () {
    renderHist(filteredRows());
    if (map) map.invalidateSize();
  });
})();
