import React from 'react';
import {Composition} from 'remotion';
import {LaunchFilm} from './LaunchFilm';

export const Root: React.FC = () => <>
  <Composition id="SchefterPortrait" component={LaunchFilm} durationInFrames={1620}
    fps={30} width={1080} height={1920} defaultProps={{feed: false}} />
  <Composition id="SchefterFeed" component={LaunchFilm} durationInFrames={1620}
    fps={30} width={1080} height={1350} defaultProps={{feed: true}} />
</>;
