export const HOTDROP_LAYERS = [
  'HotDrop_SumariBala',
  'HotDrop_Narva',
  'HotDrop_Harju',
  'HotDrop_Goose_Bay',
  'HotDrop_BlackCoast',
  'HotDrop_Fallujah',
  'HotDrop_Mutaha',
  'HotDrop_Chora',
  'HotDrop_Yehorivka',
  'HotDrop_Skorpo'
];

export function isHotdropLayer(layer) {
  return HOTDROP_LAYERS.includes(String(layer || '').trim());
}

export function listHotdropLayers() {
  return HOTDROP_LAYERS.map((layer) => ({
    name: layer.replace(/^HotDrop_/, ''),
    layerId: layer,
    classname: layer,
    source: 'cmp-hotdrop'
  }));
}
