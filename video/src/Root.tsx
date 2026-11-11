import React from "react";
import { Composition } from "remotion";
import { Preview } from "./Preview";
import { END, FPS, T } from "./theme";

export const Root: React.FC = () => (
  <Composition id="Preview" component={Preview} durationInFrames={END} fps={FPS} width={T.W} height={T.H} />
);
