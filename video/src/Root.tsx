import React from "react";
import { Composition } from "remotion";
import { Preview } from "./Preview";
import { GatesAnim, MandelbrotAnim, OneShotAnim, SECTION_FRAMES, SoftwareBenchAnim, TokenCostAnim } from "./Sections";
import { END, FPS, T } from "./theme";

export const Root: React.FC = () => (
  <>
    <Composition id="Preview" component={Preview} durationInFrames={END} fps={FPS} width={T.W} height={T.H} />
    <Composition id="OneShotAnim" component={OneShotAnim} durationInFrames={SECTION_FRAMES} fps={FPS} width={T.W} height={T.H} />
    <Composition id="MandelbrotAnim" component={MandelbrotAnim} durationInFrames={SECTION_FRAMES} fps={FPS} width={T.W} height={T.H} />
    <Composition id="SoftwareBenchAnim" component={SoftwareBenchAnim} durationInFrames={SECTION_FRAMES} fps={FPS} width={T.W} height={T.H} />
    <Composition id="TokenCostAnim" component={TokenCostAnim} durationInFrames={SECTION_FRAMES} fps={FPS} width={T.W} height={T.H} />
    <Composition id="GatesAnim" component={GatesAnim} durationInFrames={SECTION_FRAMES} fps={FPS} width={T.W} height={T.H} />
  </>
);
