"use client";

import type { AreaMeasure, Feasibility } from "@/lib/api/analysis";
import { businessDate } from "@/lib/format";
import { Disclosure, Notice, Position, PositionFigure, SectionHeader, TableScroll } from "@/components/ui";

const totalLabels:Record<string,string>={buildable:"Total Buildable Area",covered:"Total Covered Area (Apartment Space + Balcony)",
  internal:"Total Apartment Covered Area (without Balcony)",balcony:"Total Balcony Covered Area",terrace:"Total Terrace Area",
  common:"Total Common Area",garage:"Total Garage Area",building:"Total Building Area",community:"Total Community Area",
  roads_pavements:"Total Roads & Pavements Area",grand:"Grand Total Area"};
const apartmentLabels:Record<string,string>={covered:"Covered Area (including Balcony)",internal:"Covered Area (excluding Balcony)",
  balcony:"Balcony Covered Area",terrace:"Terrace Area",common:"Common Area",total:"Total Area"};
const area=(value:string|null)=>value===null ? "Not recorded / incomplete" : `${value} m²`;

function Measures({title,labels,values}:{title:string;labels:Record<string,string>;values:Record<string,AreaMeasure>}) {
  return <section><SectionHeader title={title}/><TableScroll fixedFirst label={title}><thead><tr><th scope="col">Measurement</th><th scope="col" className="num">Area m²</th><th scope="col">Basis & coverage</th></tr></thead><tbody>{Object.entries(labels).map(([key,label])=>{
    const value=values[key];return <tr key={key}><th scope="row">{label}</th><td className="num">{area(value.value)}</td><td><Disclosure title={value.value===null ? "Review missing inputs" : "Formula & source"}><p>{value.formula}</p>{value.reason ? <p>{value.reason}</p> : null}<p>{value.measured_count} / {value.expected_count} required inputs measured</p></Disclosure></td></tr>;
  })}</tbody></TableScroll></section>;
}

export function FeasibilityView({data}:{data:Feasibility}) {
  return <div className="stack">
    <SectionHeader title="Area feasibility" description={`Current inventory snapshot · ${businessDate(data.context.snapshot_as_of)} · All areas in m²`} />
    <Position><PositionFigure lead label="Number of Apartments" value={data.apartments} note="Active apartment inventory, including unreleased and sold units" />
      <PositionFigure label="Apartment covered area" value={area(data.totals.covered.value)} note="Including balconies" />
      <PositionFigure label="Buildable area" value={area(data.totals.buildable.value)} note="Apartment interiors + common area" />
    </Position>
    {!data.apartments ? <Notice tone="info">No active apartments in this inventory scope.</Notice> : null}
    {data.other_units ? <Notice tone="info">{data.other_units} other property units are excluded from apartment figures and included in building/grand totals where their measurements are complete.</Notice> : null}
    <section><SectionHeader title="Sellable & buildable area efficiency" /><TableScroll label="Area efficiency ratios"><thead><tr><th scope="col">Indicator</th><th scope="col" className="num">Ratio</th><th scope="col">Area basis</th></tr></thead><tbody>{data.efficiencies.map(row=><tr key={row.label}><th scope="row">{row.label}</th><td className="num">{row.percentage===null ? "Unavailable" : `${row.percentage}%`}</td><td><p>{row.formula}</p><p>{area(row.numerator)} / {area(row.denominator)}</p>{row.reason ? <p>{row.reason}</p> : null}</td></tr>)}</tbody></TableScroll></section>
    <Measures title="Project area totals" labels={totalLabels} values={data.totals}/>
    <Measures title="Average apartment areas" labels={Object.fromEntries(Object.entries(apartmentLabels).map(([key,label])=>[key,`Average Apartment ${label}`]))} values={data.averages}/>
    <section><SectionHeader title="Unit type → bedrooms" description="Apartment area totals grouped by the recorded unit type and bedroom count."/>
      {data.groups.length ? <TableScroll fixedFirst label="Apartment area totals by unit type and bedrooms"><thead><tr><th scope="col">Unit type</th><th scope="col">Bedrooms</th><th scope="col" className="num">Apartments</th>{Object.values(apartmentLabels).map(label=><th scope="col" className="num" key={label}>{label} m²</th>)}</tr></thead><tbody>{data.groups.map(row=><tr key={`${row.unit_type}:${row.bedrooms}`}><th scope="row">{row.unit_type}</th><td>{row.bedrooms===null ? "Not recorded" : row.bedrooms===0 ? "Studio (0)" : row.bedrooms}</td><td className="num">{row.apartments}</td>{Object.keys(apartmentLabels).map(key=><td key={key} className="num" title={row.areas[key].reason ?? row.areas[key].formula}>{area(row.areas[key].value)}</td>)}</tr>)}</tbody></TableScroll> : <p>No apartment groups recorded.</p>}
    </section>
    <Disclosure title="Definitions, source coverage & inventory entry"><ul>{data.notes.map(note=><li key={note}>{note}</li>)}</ul><p>Enter shared measurements under Inventory → Common Areas. Maintain private apartment measurements in each unit’s approved area schedule.</p></Disclosure>
  </div>;
}
