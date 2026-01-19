/**
 * D3.js Heatmap for Role Similarity Matrix
 */
import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

export default function SimilarityHeatmap({ 
  data, // { roles: string[], matrix: number[][] }
  width = 600, 
  height = 600 
}) {
  const svgRef = useRef(null)

  useEffect(() => {
    if (!data || !data.roles || !data.matrix) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const margin = { top: 100, right: 30, bottom: 30, left: 120 }
    const innerWidth = width - margin.left - margin.right
    const innerHeight = height - margin.top - margin.bottom

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`)

    const roles = data.roles
    const matrix = data.matrix

    // Scales
    const x = d3.scaleBand()
      .domain(roles)
      .range([0, innerWidth])
      .padding(0.05)

    const y = d3.scaleBand()
      .domain(roles)
      .range([0, innerHeight])
      .padding(0.05)

    const colorScale = d3.scaleSequential()
      .domain([0, 1])
      .interpolator(d3.interpolateRdYlGn)

    // Flatten matrix data for rectangles
    const cells = []
    matrix.forEach((row, i) => {
      row.forEach((value, j) => {
        cells.push({
          row: roles[i],
          col: roles[j],
          value: value
        })
      })
    })

    // Create cells
    g.selectAll('rect')
      .data(cells)
      .join('rect')
      .attr('x', d => x(d.col))
      .attr('y', d => y(d.row))
      .attr('width', x.bandwidth())
      .attr('height', y.bandwidth())
      .attr('fill', d => colorScale(d.value))
      .attr('stroke', '#fff')
      .attr('stroke-width', 1)
      .style('cursor', 'pointer')
      .on('mouseover', function(event, d) {
        d3.select(this)
          .attr('stroke', '#000')
          .attr('stroke-width', 2)
        
        // Show tooltip
        const tooltip = d3.select('#heatmap-tooltip')
        tooltip
          .style('opacity', 1)
          .html(`
            <strong>${d.row}</strong> ↔ <strong>${d.col}</strong><br/>
            Similarity: ${(d.value * 100).toFixed(1)}%
          `)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px')
      })
      .on('mouseout', function() {
        d3.select(this)
          .attr('stroke', '#fff')
          .attr('stroke-width', 1)
        
        d3.select('#heatmap-tooltip').style('opacity', 0)
      })

    // X axis
    g.append('g')
      .attr('transform', `translate(0,0)`)
      .call(d3.axisTop(x))
      .selectAll('text')
      .attr('transform', 'rotate(-45)')
      .style('text-anchor', 'start')
      .attr('dx', '0.5em')
      .attr('dy', '0.5em')
      .style('font-size', '10px')

    // Y axis
    g.append('g')
      .call(d3.axisLeft(y))
      .selectAll('text')
      .style('font-size', '10px')

    // Color legend
    const legendWidth = 200
    const legendHeight = 10
    
    const legendScale = d3.scaleLinear()
      .domain([0, 1])
      .range([0, legendWidth])

    const legendAxis = d3.axisBottom(legendScale)
      .ticks(5)
      .tickFormat(d => `${(d * 100).toFixed(0)}%`)

    const defs = svg.append('defs')
    const gradient = defs.append('linearGradient')
      .attr('id', 'heatmap-gradient')

    gradient.selectAll('stop')
      .data(d3.range(0, 1.1, 0.1))
      .join('stop')
      .attr('offset', d => `${d * 100}%`)
      .attr('stop-color', d => colorScale(d))

    const legend = svg.append('g')
      .attr('transform', `translate(${margin.left + innerWidth/2 - legendWidth/2}, ${height - 25})`)

    legend.append('rect')
      .attr('width', legendWidth)
      .attr('height', legendHeight)
      .style('fill', 'url(#heatmap-gradient)')

    legend.append('g')
      .attr('transform', `translate(0, ${legendHeight})`)
      .call(legendAxis)
      .selectAll('text')
      .style('font-size', '9px')

    legend.append('text')
      .attr('x', legendWidth / 2)
      .attr('y', -5)
      .attr('text-anchor', 'middle')
      .style('font-size', '11px')
      .style('fill', '#666')
      .text('Similarity')

  }, [data, width, height])

  if (!data) {
    return (
      <div className="flex items-center justify-center h-96 bg-gray-50 rounded-lg">
        <p className="text-gray-500">No similarity data available</p>
      </div>
    )
  }

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        width={width}
        height={height}
        style={{ maxWidth: '100%', height: 'auto' }}
      />
      <div
        id="heatmap-tooltip"
        className="absolute bg-gray-900 text-white text-xs px-2 py-1 rounded shadow-lg pointer-events-none"
        style={{ opacity: 0, transition: 'opacity 0.2s' }}
      />
    </div>
  )
}
