"""
OmicEngine — Julia multi-omic binder scores (Phase 2).

S_omic = σ(α S_off + β S_path + γ S_gen)

Python owns orchestration; this package is pure sparse-matrix compute.
"""
module OmicEngine

using SparseArrays
using LinearAlgebra

export soff, spath, sgen, somic

"""Off-target load: sum w(affinity) for off-target flags."""
function soff(affinities_nm::AbstractVector{<:Real}, is_off::AbstractVector{Bool};
              eps::Float64=1e-9)
    @assert length(affinities_nm) == length(is_off)
    s = 0.0
    @inbounds for i in eachindex(affinities_nm)
        if is_off[i]
            # stronger binding (lower nM) → higher weight
            s += 1.0 / (log10(affinities_nm[i] + 1.0) + eps)
        end
    end
    return s
end

"""Pathway burden: sum tox_weight for pathways hit by drug targets."""
function spath(pathway_hits::AbstractVector{Bool}, tox_weights::AbstractVector{<:Real})
    @assert length(pathway_hits) == length(tox_weights)
    s = 0.0
    @inbounds for i in eachindex(pathway_hits)
        if pathway_hits[i]
            s += tox_weights[i]
        end
    end
    return s
end

"""Variant load related to a PT."""
function sgen(effect_sizes::AbstractVector{<:Real}, related_mask::AbstractVector{Bool})
    @assert length(effect_sizes) == length(related_mask)
    s = 0.0
    @inbounds for i in eachindex(effect_sizes)
        if related_mask[i]
            s += abs(effect_sizes[i])
        end
    end
    return s
end

σ(x) = 1 / (1 + exp(-x))

function somic(s_off::Real, s_path::Real, s_gen::Real;
               α::Float64=1.0, β::Float64=1.0, γ::Float64=1.0)
    return σ(α * s_off + β * s_path + γ * s_gen)
end

end # module
