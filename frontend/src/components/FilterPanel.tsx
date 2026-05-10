import type { DashboardFilters } from "../useDashboardState";

type Props = {
  counties: string[];
  filters: DashboardFilters;
  onChange: (filters: DashboardFilters) => void;
};

export function FilterPanel({ counties, filters, onChange }: Props) {
  return (
    <section className="panel-section">
      <h2>Filters</h2>
      <div className="control-group">
        <label>
          County
          <select
            value={filters.county}
            onChange={(event) => onChange({ ...filters, county: event.target.value })}
          >
            <option value="">All counties</option>
            {counties.map((county) => (
              <option key={county} value={county}>
                {county}
              </option>
            ))}
          </select>
        </label>
        <label>
          Score layer
          <select
            value={filters.scoreType}
            onChange={(event) =>
              onChange({ ...filters, scoreType: event.target.value as DashboardFilters["scoreType"] })
            }
          >
            <option value="civic_access_index">Civic Access Index</option>
            <option value="healthcare_access_score">Healthcare gap</option>
            <option value="food_access_score">Food gap</option>
            <option value="transit_access_score">Transit gap</option>
            <option value="vulnerability_score">Socioeconomic vulnerability</option>
          </select>
        </label>
        <label>
          Minimum score
          <input
            type="range"
            min="0"
            max="100"
            value={filters.minScore}
            onChange={(event) => onChange({ ...filters, minScore: Number(event.target.value) })}
          />
          <span className="range-value">{filters.minScore}</span>
        </label>
      </div>
    </section>
  );
}
