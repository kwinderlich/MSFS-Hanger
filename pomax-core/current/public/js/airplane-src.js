export const defaultPlane = `GA-Single.png`;

function text(v) {
  return String(v || ``).toLowerCase();
}

function typeBasedPicture(model = {}) {
  const subtype = text(model.subtype || model.category || model.type);
  const title = text(model.title);
  const engineType = text(model.engineType);
  const engineCount = Number(model.engineCount || 0);
  const isFloat = !!model.isFloatPlane || title.includes(`float`) || title.includes(`amphibian`);
  const isHeli = subtype.includes(`helicopter`) || subtype.includes(`heli`) || title.includes(`helicopter`) || engineType.includes(`helicopter`);
  const isBusiness = subtype.includes(`business`) || title.includes(`citation`) || title.includes(`lear`) || title.includes(`gulfstream`) || title.includes(`phenom`) || title.includes(`hondajet`);
  const isAirliner = subtype.includes(`airliner`) || subtype.includes(`airline`) || title.includes(`airbus`) || title.includes(`boeing`) || /(727|737|747|757|767|777|787|a220|a300|a310|a318|a319|a320|a321|a330|a340|a350|a380)/.test(title);

  if (isFloat) return `Float.png`;
  if (isHeli) return `Helicopter.png`;
  if (isBusiness) return `Business.png`;
  if (isAirliner) return `Airliner.png`;
  if (engineCount > 1) return `GA-Multi.png`;
  return `GA-Single.png`;
}

export function getAirplaneSrc(modelOrTitle = ``) {
  if (typeof modelOrTitle === `object` && modelOrTitle) {
    return typeBasedPicture(modelOrTitle);
  }
  return typeBasedPicture({ title: modelOrTitle });
}
