import {
  constrainMap,
  getCompassDiff,
  lerp,
} from "../utils/utils.js";

const { abs, sign } = Math;
const USE_SIM_AP = process.env.HANGAR_USE_SIM_AP !== `0`;
const FEATURES = {
  FLY_SPECIFIC_HEADING: true,
};

// Conservative route-capture controller.
// Prior builds used the more aggressive adaptive max-stick logic from the later
// tutorial iterations. In live MSFS 2024 testing this could over-hunt badly
// during initial waypoint capture, producing circles around the first leg.
// This version intentionally falls back to the simpler turn-rate controller from
// the tutorial's successful mid-stage refinement, with stick smoothing so it is
// stable enough for normal GA and light twin route following.
export async function flyLevel(autopilot, state) {
  const { api, waypoints } = autopilot;
  const landing = waypoints.isLanding();
  const { data: flightData, model: flightModel } = state;
  const { aileron, turnRate, heading } = flightData;
  const parameters = Object.assign({ autopilot }, flightModel, flightData);
  const { headingDiff, targetHeading } = getTargetHeading(parameters, landing);

  // For the integrated Hangar build, rely on the simulator's native heading
  // autopilot while Pomax computes the route heading. This avoids the endless
  // orbiting we saw when directly commanding aileron in MSFS 2024.
  if (USE_SIM_AP) {
    api.set(`AUTOPILOT_HEADING_LOCK_DIR`, targetHeading);
    api.trigger(`AP_HDG_HOLD_ON`);
    api.trigger("AILERON_SET", 0);
    autopilot.__hangarDebugTick = (autopilot.__hangarDebugTick || 0) + 1;
    if (autopilot.__hangarDebugTick % 12 === 0 && abs(headingDiff) > 3) {
      console.log(`[api] route capture current=${Number(heading).toFixed(1)} target=${Number(targetHeading).toFixed(1)} diff=${Number(headingDiff).toFixed(1)} turnRate=${Number(turnRate).toFixed(2)} aileron=0 axis=sim-ap-hdg`);
    }
    return;
  }

  // Clamp desired turn-rate to standard-rate-ish behaviour.
  const targetTurnRate = constrainMap(headingDiff, -20, 20, -3, 3);
  const turnDiff = targetTurnRate - turnRate;
  let proportion = constrainMap(turnDiff, -3, 3, -1, 1);
  proportion = sign(proportion) * abs(proportion);
  const maxStick = 16384 / 5;
  const targetAileron = proportion * maxStick;

  const currentAileron = (Number(aileron) / 100) * (2 ** 14);
  const aileronDiff = abs(currentAileron - targetAileron);
  const ratio = constrainMap(aileronDiff, 0, abs(maxStick), 1, 0) ** 0.5;
  const mixed = lerp(ratio, currentAileron, targetAileron);

  autopilot.__hangarDebugTick = (autopilot.__hangarDebugTick || 0) + 1;
  if (autopilot.__hangarDebugTick % 12 === 0 && abs(headingDiff) > 3) {
    console.log(`[api] route capture current=${Number(heading).toFixed(1)} target=${Number(targetHeading).toFixed(1)} diff=${Number(headingDiff).toFixed(1)} turnRate=${Number(turnRate).toFixed(2)} aileron=${(mixed|0)} axis=custom-aileron`);
  }

  api.trigger("AILERON_SET", mixed | 0);
}

function getTargetHeading(parameters, landing) {
  const { autopilot, heading, flightHeading, speed, vs1, cruiseSpeed } = parameters;
  let targetHeading = heading;
  let headingDiff = 0;
  if (FEATURES.FLY_SPECIFIC_HEADING) {
    targetHeading = autopilot.waypoints.getHeading(parameters);
    headingDiff = getCompassDiff(landing ? flightHeading : heading, targetHeading);
    if (!landing) {
      const half = headingDiff / 2;
      headingDiff = constrainMap(speed, vs1, cruiseSpeed, half, headingDiff);
    }
  }
  return { targetHeading, headingDiff };
}
