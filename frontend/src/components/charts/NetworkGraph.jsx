/**
 * D3.js Force-Directed Network Graph for Skill Connections
 * Shows how skills relate to each other based on co-occurrence
 */
import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import { CHART_COLORS, getCategoryColor } from '../../utils/helpers'

export default function SkillNetworkGraph({ 
  data, 
  width = 800, 
  height = 600,
  onNodeClick = () => {}
}) {
  const svgRef = useRef(null)
  const [tooltip, setTooltip] = useState({ show: false, x: 0, y: 0, content: '' })

  useEffect(() => {
    if (!data || !data.nodes || !data.links || data.nodes.length === 0) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    // Create container group for zoom
    const g = svg.append('g')

    // Add zoom behavior
    const zoom = d3.zoom()
      .scaleExtent([0.3, 3])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })
    
    svg.call(zoom)

    // Get unique categories for coloring
    const categories = [...new Set(data.nodes.map(n => n.category))]
    const colorScale = d3.scaleOrdinal()
      .domain(categories)
      .range(CHART_COLORS)

    // Calculate node sizes based on connection count
    const maxCount = Math.max(...data.nodes.map(n => n.count || 1))
    const nodeScale = d3.scaleSqrt()
      .domain([1, maxCount])
      .range([8, 30])

    // Calculate link widths based on weight
    const maxWeight = Math.max(...data.links.map(l => l.weight || 1))
    const linkScale = d3.scaleLinear()
      .domain([1, maxWeight])
      .range([1, 6])

    // Create force simulation
    const simulation = d3.forceSimulation(data.nodes)
      .force('link', d3.forceLink(data.links)
        .id(d => d.id)
        .distance(100)
        .strength(d => d.similarity || 0.5)
      )
      .force('charge', d3.forceManyBody()
        .strength(-200)
        .distanceMax(300)
      )
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide()
        .radius(d => nodeScale(d.count || 1) + 5)
      )

    // Create links
    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(data.links)
      .join('line')
      .attr('stroke', '#94a3b8')
      .attr('stroke-opacity', 0.4)
      .attr('stroke-width', d => linkScale(d.weight || 1))

    // Create nodes group
    const node = g.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(data.nodes)
      .join('g')
      .attr('class', 'node')
      .call(d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended)
      )

    // Add circles to nodes
    node.append('circle')
      .attr('r', d => nodeScale(d.count || 1))
      .attr('fill', d => colorScale(d.category))
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .on('mouseover', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('r', nodeScale(d.count || 1) * 1.3)
        
        // Highlight connected links
        link.attr('stroke-opacity', l => 
          l.source.id === d.id || l.target.id === d.id ? 0.8 : 0.1
        )

        setTooltip({
          show: true,
          x: event.pageX,
          y: event.pageY,
          content: `${d.id}\nCategory: ${d.category}\nConnections: ${d.count}`
        })
      })
      .on('mouseout', function(event, d) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('r', nodeScale(d.count || 1))
        
        link.attr('stroke-opacity', 0.4)
        setTooltip({ show: false, x: 0, y: 0, content: '' })
      })
      .on('click', (event, d) => {
        onNodeClick(d.id)
      })

    // Add labels to nodes
    node.append('text')
      .text(d => d.id)
      .attr('x', d => nodeScale(d.count || 1) + 5)
      .attr('y', 4)
      .attr('font-size', '10px')
      .attr('fill', '#374151')
      .style('pointer-events', 'none')

    // Update positions on tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)

      node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    // Drag functions
    function dragstarted(event, d) {
      if (!event.active) simulation.alphaTarget(0.3).restart()
      d.fx = d.x
      d.fy = d.y
    }

    function dragged(event, d) {
      d.fx = event.x
      d.fy = event.y
    }

    function dragended(event, d) {
      if (!event.active) simulation.alphaTarget(0)
      d.fx = null
      d.fy = null
    }

    // Cleanup
    return () => {
      simulation.stop()
    }
  }, [data, width, height, onNodeClick])

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="bg-gray-50 rounded-lg"
        style={{ maxWidth: '100%', height: 'auto' }}
      />
      
      {/* Tooltip */}
      {tooltip.show && (
        <div 
          className="absolute bg-gray-900 text-white text-xs px-2 py-1 rounded shadow-lg pointer-events-none whitespace-pre-line"
          style={{
            left: tooltip.x + 10,
            top: tooltip.y - 10,
            transform: 'translate(-50%, -100%)'
          }}
        >
          {tooltip.content}
        </div>
      )}

      {/* Legend */}
      {data?.nodes && (
        <div className="absolute top-4 right-4 bg-white/90 rounded-lg p-3 shadow-sm">
          <h4 className="text-xs font-medium text-gray-700 mb-2">Categories</h4>
          <div className="space-y-1">
            {[...new Set(data.nodes.map(n => n.category))].slice(0, 6).map((cat, i) => (
              <div key={cat} className="flex items-center gap-2 text-xs">
                <div 
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                />
                <span className="text-gray-600">{cat}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Instructions */}
      <div className="absolute bottom-4 left-4 text-xs text-gray-500">
        Drag to move nodes • Scroll to zoom • Click node to select
      </div>
    </div>
  )
}
