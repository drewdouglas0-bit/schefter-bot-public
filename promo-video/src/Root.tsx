import React from 'react';
import {Composition} from 'remotion';
import {LaunchFilm} from './LaunchFilm';
import {CLEAN_DURATION,CleanFilm,TRADE_DURATION} from './CleanFilm';

export const Root: React.FC = () => <>
  <Composition id="SchefterPortrait" component={LaunchFilm} durationInFrames={1620}
    fps={30} width={1080} height={1920} defaultProps={{feed: false}} />
  <Composition id="SchefterFeed" component={LaunchFilm} durationInFrames={1620}
    fps={30} width={1080} height={1350} defaultProps={{feed: true}} />
  <Composition id="SchefterCleanPortrait" component={CleanFilm} durationInFrames={CLEAN_DURATION}
    fps={30} width={1080} height={1920} />
  <Composition id="SchefterCleanFeed" component={CleanFilm} durationInFrames={CLEAN_DURATION}
    fps={30} width={1080} height={1350} />
  <Composition id="SchefterTradePortrait" component={CleanFilm} durationInFrames={TRADE_DURATION}
    fps={30} width={1080} height={1920} defaultProps={{variant:'trade' as const}} />
  <Composition id="SchefterTradeFeed" component={CleanFilm} durationInFrames={TRADE_DURATION}
    fps={30} width={1080} height={1350} defaultProps={{variant:'trade' as const}} />
</>;
