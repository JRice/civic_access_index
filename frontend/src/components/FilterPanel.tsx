export function FilterPanel() {
  return (
    <section>
      <h2>Filters</h2>
      <div className="control-group">
        <label>
          County
          <select defaultValue="">
            <option value="">All counties</option>
          </select>
        </label>
        <label>
          Score type
          <select defaultValue="civic_access_index">
            <option value="civic_access_index">Civic Access Index</option>
            <option value="healthcare_access_score">Healthcare</option>
            <option value="food_access_score">Food</option>
            <option value="transit_access_score">Transit</option>
          </select>
        </label>
        <label>
          Minimum score
          <input type="number" min="0" max="100" defaultValue="70" />
        </label>
        <button type="button">Apply</button>
      </div>
    </section>
  );
}

