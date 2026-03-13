export interface VehicleModelOption {
  make: string;
  models: string[];
}

export const VEHICLE_MAKE_MODEL_OPTIONS: VehicleModelOption[] = [
  {
    make: 'Toyota',
    models: ['Camry', 'Corolla', 'RAV4', 'Highlander', 'Tacoma', 'Tundra', 'Prius', '4Runner', 'Sienna'],
  },
  {
    make: 'Honda',
    models: ['Civic', 'Accord', 'CR-V', 'HR-V', 'Pilot', 'Odyssey', 'Ridgeline'],
  },
  {
    make: 'Ford',
    models: ['F-150', 'Escape', 'Explorer', 'Mustang', 'Edge', 'Bronco Sport', 'Ranger'],
  },
  {
    make: 'Chevrolet',
    models: ['Silverado 1500', 'Equinox', 'Tahoe', 'Suburban', 'Traverse', 'Malibu', 'Trailblazer'],
  },
  {
    make: 'Nissan',
    models: ['Altima', 'Sentra', 'Rogue', 'Murano', 'Pathfinder', 'Frontier'],
  },
  {
    make: 'Hyundai',
    models: ['Elantra', 'Sonata', 'Tucson', 'Santa Fe', 'Palisade', 'Kona'],
  },
  {
    make: 'Kia',
    models: ['Forte', 'K5', 'Sportage', 'Sorento', 'Telluride', 'Seltos'],
  },
  {
    make: 'Subaru',
    models: ['Outback', 'Forester', 'Crosstrek', 'Impreza', 'Ascent', 'Legacy'],
  },
  {
    make: 'Jeep',
    models: ['Wrangler', 'Grand Cherokee', 'Cherokee', 'Compass', 'Gladiator', 'Renegade'],
  },
  {
    make: 'GMC',
    models: ['Sierra 1500', 'Yukon', 'Acadia', 'Terrain', 'Canyon'],
  },
  {
    make: 'Ram',
    models: ['1500', '2500', '3500', 'ProMaster'],
  },
  {
    make: 'Volkswagen',
    models: ['Jetta', 'Golf', 'GTI', 'Tiguan', 'Atlas', 'Taos'],
  },
  {
    make: 'Mazda',
    models: ['Mazda3', 'CX-30', 'CX-5', 'CX-50', 'CX-9'],
  },
  {
    make: 'BMW',
    models: ['3 Series', '5 Series', 'X1', 'X3', 'X5'],
  },
  {
    make: 'Mercedes-Benz',
    models: ['C-Class', 'E-Class', 'GLC', 'GLE', 'GLS'],
  },
  {
    make: 'Audi',
    models: ['A4', 'A6', 'Q3', 'Q5', 'Q7'],
  },
  {
    make: 'Lexus',
    models: ['ES', 'IS', 'RX', 'NX', 'GX', 'LX'],
  },
  {
    make: 'Acura',
    models: ['Integra', 'TLX', 'RDX', 'MDX'],
  },
  {
    make: 'Tesla',
    models: ['Model 3', 'Model Y', 'Model S', 'Model X'],
  },
];

/** Common vehicle colors for dropdowns */
export const COMMON_COLORS = [
  'Black', 'White', 'Silver', 'Gray', 'Red', 'Blue', 'Navy', 'Brown', 'Green',
  'Beige', 'Orange', 'Yellow', 'Gold', 'Burgundy', 'Charcoal', 'Pearl', 'Other',
];

