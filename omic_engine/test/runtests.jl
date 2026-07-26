using Test
using OmicEngine

@testset "S_off / S_path / S_gen / S_omic" begin
    affinities = [10.0, 100.0, 5.0]
    is_off = [false, true, true]
    s_off = soff(affinities, is_off)
    @test s_off > 0

    hits = [true, false, true]
    tox = [1.0, 0.5, 2.0]
    @test spath(hits, tox) ≈ 3.0

    effects = [0.8, 0.1, 0.5]
    related = [true, false, true]
    @test sgen(effects, related) ≈ 1.3

    s = somic(1.0, 1.0, 1.0)
    @test 0.0 < s < 1.0
end
