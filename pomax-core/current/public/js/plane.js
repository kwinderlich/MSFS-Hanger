import { Questions } from "./questions.js";
import { map as defaultMap, DUNCAN_AIRPORT, targetInfo } from "./map.js";
import { MapMarker } from "./map-marker.js";
import { getAirplaneSrc } from "./airplane-src.js";
import { Trail } from "./trail.js";
import { Attitude } from "./attitude.js";
import { initCharts } from "./dashboard/charts.js";
import { Autopilot } from "./autopilot.js";
import { WaypointOverlay } from "./waypoint-overlay.js";
import { getDistanceBetweenPoints, KM_PER_NM } from "./utils.js";

const { abs, sqrt, min } = Math;

export class Plane {
  constructor(
    server,
    map = defaultMap,
    location = DUNCAN_AIRPORT,
    heading = 135
  ) {
    this.server = server;
    this.map = map;
    this.lastUpdate = {
      lat: 0,
      long: 0,
      flying: false,
      crashed: false,
    };
    this.addPlaneIconToMap(map, location, heading);
    // Set up our chart solution, which will inject some elements
    // into the page that will do the relevant drawing for us:
    this.charts = initCharts();
    this.autopilot = new Autopilot(this);
    this.waypointOverlay = new WaypointOverlay(this);
    this.setupControls(map);

    // add a little "this point is ...NM and ...h:m away" on mouse move
    map.on(`mousemove`, ({ latlng }) => {
      const flightData = this.state.flightInformation.data;
      const { lat: lat1, long: lng1, speed } = flightData;
      const { lat: lat2, lng: lng2 } = latlng;

      const dist = getDistanceBetweenPoints(lat1, lng1, lat2, lng2),
        nm = dist / KM_PER_NM,
        duration = nm / speed,
        h = duration | 0,
        m = ((duration - h) * 60) | 0,
        hs = m === 1 ? `` : `s`,
        ms = m === 1 ? `` : `s`;

        if (nm < 1) return targetInfo.updateInnerHTML();

        if (h === 0) {
        if (m < 2) return targetInfo.updateInnerHTML();
        targetInfo.updateInnerHTML(`${nm.toFixed(2)}NM, ${m} minute${ms} away`);
      } else {
        targetInfo.updateInnerHTML(
          `${nm.toFixed(2)}NM, ${h} hour${hs}, ${m} minute${ms} away`
        );
      }
    });
  }

  setupControls(map) {
    this.centerMapOnPlane = true;
    this.showTrail = true;
    this.zoomToRoute = false;
    this.zoomToAircraft = false;
    this._lastRouteFit = 0;
    this._hangarApiBase = globalThis.__hangarApiBase || 'http://127.0.0.1:7891';
    const btn = (this.centerButton =
      document.getElementById(`center-on-plane`));
    btn.addEventListener(`change`, ({ target }) => {
      this.centerMapOnPlane = !!target.checked;
    });
    map.on(`drag`, () => {
      if (btn.checked) btn.click();
    });
    if (!btn.checked) btn.click();
    const trailBox = document.getElementById(`show-trail`);
    if (trailBox) {
      this.showTrail = !!trailBox.checked;
      trailBox.addEventListener(`change`, ({ target }) => {
        this.setTrailVisible(!!target.checked);
      });
    }
    const zoomAircraftBtn = document.getElementById(`zoom-to-aircraft`);
    if (zoomAircraftBtn) {
      zoomAircraftBtn.addEventListener(`click`, () => this.requestZoomToAircraft());
    }
    const zoomRouteBtn = document.getElementById(`zoom-to-route`);
    if (zoomRouteBtn) {
      zoomRouteBtn.addEventListener(`click`, () => this.requestZoomToRoute());
    }
    const pauseBtn = document.getElementById(`pause-sim`);
    if (pauseBtn) {
      this.pauseButton = pauseBtn;
      pauseBtn.addEventListener(`click`, async () => {
        const desiredPaused = !pauseBtn.classList.contains(`active`);
        pauseBtn.disabled = true;
        try {
          await fetch(`${this._hangarApiBase}/api/pomax/command`, {
            method: `POST`,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: desiredPaused ? `pause_on` : `pause_off` }),
          });
        } catch (e) {
          console.error(`Could not toggle simulator pause`, e);
        } finally {
          setTimeout(() => { pauseBtn.disabled = false; }, 500);
        }
      });
    }
  }

  updatePauseButton(paused) {
    const btn = this.pauseButton;
    if (!btn) return;
    btn.classList.toggle(`active`, !!paused);
    btn.textContent = paused ? `Resume Sim` : `Pause Sim`;
  }

  setTrailVisible(value) {
    this.showTrail = value !== false;
    if (this.trail?.setVisible) this.trail.setVisible(this.showTrail);
  }

  /**
   * We'll use Leaflet's "icon" functionality to add our plane:
   */
  async addPlaneIconToMap(map, location, heading) {
    const props = {
      icon: L.divIcon({
        iconSize: [36, 25],
        iconAnchor: [36 / 2, 25 / 2],
        className: `map-pin`,
        // We our little plane icon's HTML, with the initial heading baked in:
        html: MapMarker.getHTML(heading),
      }),
    };
    // Then we turn that into a Leaflet map marker:
    this.marker = L.marker(location, props).addTo(map);
    // And then we cache the resulting page element so we can use it later, too:
    this.planeIcon = document.querySelector(`#plane-icon`);
  }

  /**
   * A little helper function for tracking "the current trail", because we
   * can restart flights as much as we want (voluntarily, or because we
   * crashed) and those new flights should all get their own trail:
   */
  startNewTrail(location) {
    this.trail = new Trail(this.map, location);
    this.trail?.setVisible?.(this.showTrail !== false);
  }

  /**
   * We've seen this function before!
   */
  async updateState(state) {
    this.state = state;
    const now = Date.now();
    const prev = this.lastUpdate.time || now - 1000;
    if (now - prev < 100) return;
    Questions.update(state);

    // Check if we started a new flight because that requires
    // immediately building a new flight trail:
    try {
      const { flying: wasFlying } = this.lastUpdate.flightInformation.general;
      const { flying } = this.state.flightInformation.general;
      const startedFlying = !wasFlying && flying;
      if (startedFlying) this.startNewTrail();
    } catch (e) {
      // this will fail if we don't have lastUpdate yet, and that's fine.
    }

    // Keep our map up to date:
    this.updateMap(now, state.flightInformation);

    const flightData = state.flightInformation.data;
    if (flightData) {
      // Update the attitude indicator:
      const { pitch, bank } = state.flightInformation.data;
      Attitude.setPitchBank(pitch, bank);

      // Update our science
      this.updateChart(flightData);
    }

    // Super straight-forward:
    const { autopilot: params } = state;
    this.autopilot.update(flightData, params);
    this.waypointOverlay.manage(params?.waypoints, params?.waypointsRepeat);
    const simApWarning = document.getElementById(`sim-ap-warning`);
    if (simApWarning) simApWarning.classList.toggle(`hidden`, !flightData?.MASTER);
    const pausedState = (typeof state?.paused === `boolean`)
      ? state.paused
      : !!state?.flightInformation?.general?.paused;
    this.updatePauseButton(pausedState);

    this.lastUpdate = { time: now, ...state };
  }

  /**
   * A dedicated function for updating the map!
   */
  async updateMap(now, { model: flightModel, data: flightData, general }) {
    if (!flightData) return;

    const { map, marker, planeIcon } = this;
    const { cruiseSpeed } = flightModel;
    const { lat, long, speed } = flightData;

    // Do we have a GPS coordinate? (And not the 0,0 off the West coast
    // of Africa that you get while you're not in game?)
    if (lat === undefined || long === undefined) return;
    if (abs(lat) < 0.1 && abs(long) < 0.1) return;

    // Then, did we teleport?
    if (this.lastUpdate && this.trail) {
      const [lat2, long2] = this.trail.getLast() || [lat, long];
      const d = getDistanceBetweenPoints(lat, long, lat2, long2);
      if (d > 1) this.startNewTrail([lat, long]);
    }

    // With all that done, we can add the current position to our current trail:
    if (!this.trail) this.startNewTrail([lat, long]);
    this.trail.add(lat, long);

    // Update our plane's position on the Leaflet map:
    marker.setLatLng([lat, long]);

    // Adjust the viewport. In normal mode we keep the plane centered.
    // In route-zoom mode we fit the plane + all visible waypoints so the
    // whole route stays in view.
    if (this.zoomToRoute && Array.isArray(this.waypointOverlay?.waypoints) && this.waypointOverlay.waypoints.length) {
      const nowFit = Date.now();
      if (!this._lastRouteFit || nowFit - this._lastRouteFit > 900) {
        const pts = [[lat, long], ...this.waypointOverlay.waypoints.map((w) => [w.lat, w.long]).filter((pt) => Number.isFinite(pt[0]) && Number.isFinite(pt[1]))];
        const bounds = L.latLngBounds(pts);
        if (bounds.isValid()) map.fitBounds(bounds.pad(0.12), { animate: false, maxZoom: 12.8 });
        this._lastRouteFit = nowFit;
      }
    } else if (this.centerMapOnPlane) {
      if (this.zoomToAircraft) map.setView([lat, long], 17.6, { animate: false });
      else map.setView([lat, long]);
    }

    // And set some classes that let us show pause/crash states:
    const { paused, crashed } = general;
    planeIcon.classList.toggle(`paused`, !!paused);
    planeIcon.classList.toggle(`crashed`, !!crashed);

    // Also, make sure we're using the right silhouette image:
    const pic = getAirplaneSrc(flightModel);
    [...planeIcon.querySelectorAll(`img`)].forEach(
      (img) => (img.src = `planes/${pic}`)
    );

    // Then update the marker's CSS variables and various text bits:
    this.updateMarker(planeIcon, flightData);
  }

  /**
   * Show waypoints on the map, and allow the user to add, configure,
   * and remove waypoints.
   */
  updateWaypoints(waypoints) {}

  /**
   * A dedicated function for updating the marker, which right now means
   * updating the CSS variables we're using to show our plane and shadow.
   */
  updateMarker(planeIcon, flightData) {
    const css = planeIcon.style;

    const { alt, headingBug, groundAlt, lift } = flightData;
    const { heading, speed, trueHeading } = flightData;

    css.setProperty(`--altitude`, alt | 0);
    css.setProperty(`--sqrt-alt`, sqrt(alt) | 0);
    css.setProperty(`--speed`, speed | 0);
    css.setProperty(`--north`, trueHeading - heading);
    css.setProperty(`--heading`, heading);
    css.setProperty(`--heading-bug`, headingBug);

    const altitudeText =
      (groundAlt | 0) === 0
        ? `${alt | 0}'`
        : `${(alt - groundAlt) | 0}' (${alt | 0}')`;
    planeIcon.querySelector(`.alt`).textContent = altitudeText;
    planeIcon.querySelector(`.speed`).textContent = `${speed | 0}kts`;
  }

  /**
   * And then in the updateChart function we simply pick our
   * values, and tell the charting solution to plot them.
   */
  updateChart(flightData) {
    const { alt, bank, groundAlt, pitch } = flightData;
    const { throttle, speed, heading, rudder } = flightData;
    const { VS, pitchTrim, aileronTrim, turnRate, rudderTrim } = flightData;
    const nullDelta = { VS: 0, pitch: 0, bank: 0 };
    const { VS: dVS, pitch: dPitch, bank: dBank } = flightData.d ?? nullDelta;

    this.charts.update({
      // basics
      ground: groundAlt,
      altitude: alt,
      throttle,
      speed,
      // elevator
      VS,
      dVS,
      pitch,
      dPitch,
      // ailleron
      heading,
      bank,
      dBank,
      turnRate,
      rudder,
      //trim
      pitchTrim,
      aileronTrim,
      rudderTrim,
    });

    // and a special call to dual-plot the ground in the altitude graph
    this.charts.updateChart(`altitude`, groundAlt, { limit: true });
  }
}
