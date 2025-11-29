import React, { useEffect, useState } from 'react';
import { trackEvent, trackPageView } from './ga4';
import { marked } from 'marked';

const API_BASE = (
	process.env.REACT_APP_API_URL || 'http://127.0.0.1:5000'
).replace(/\/$/, '');

const KO_FI_URL = 'https://ko-fi.com/nikharbhavsar';

function App() {
	const [situationText, setSituationText] = useState('');
	const [mode, setMode] = useState('normal'); // "normal" | "deep"
	const [loading, setLoading] = useState(false);
	const [result, setResult] = useState(null);
	const [error, setError] = useState('');

	useEffect(() => {
		trackPageView('/');
	}, []);

	const handleDonateClick = () => {
		trackEvent({
			action: 'click_donate',
			category: 'support',
			label: 'kofi_button',
		});

		window.open(KO_FI_URL, '_blank', 'noopener,noreferrer');
	};

	const handleSubmit = async (e) => {
		e.preventDefault();
		setError('');
		setResult(null);

		const trimmed = situationText.trim();
		if (!trimmed) {
			setError('Please describe your situation.');
			return;
		}

		setLoading(true);
		const endpoint = mode === 'deep' ? '/api/help/deep' : '/api/help';
		const url = `${API_BASE}${endpoint}`;

		console.log('Calling API:', url, { mode });

		trackEvent({
			action: 'submit_help_request',
			category: 'help',
			label: mode,
		});

		try {
			const res = await fetch(url, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ situationText: trimmed }),
			});

			if (!res.ok) {
				throw new Error(`API error: ${res.status}`);
			}

			const data = await res.json();
			setResult(data);

			trackEvent({
				action: 'help_request_success',
				category: 'help',
				label: data.hazard || 'unknown',
			});
		} catch (err) {
			console.error('Request failed:', err);
			setError('Something went wrong. Please try again.');

			trackEvent({
				action: 'help_request_error',
				category: 'help',
				label: err?.message || 'unknown_error',
			});
		} finally {
			setLoading(false);
		}
	};

	const handleReset = () => {
		setSituationText('');
		setResult(null);
		setError('');
        setMode('normal');

		trackEvent({
			action: 'help_form_reset',
			category: 'help',
			label: 'reset',
		});
	};

	const resultMode = result?.mode || mode;

	return (
		<div className='app'>
			<header className='app-header'>
				<div className='app-header__titles app-header__titles--center'>
					<span className='badge badge--pill'>AI • Safety Assistant</span>
					<h1 className='app-header__title'>Emergency Safety Helper</h1>
				</div>
				<p className='app-header__subtitle'>
					Describe what&apos;s happening and get calm, step-by-step, non-medical
					safety guidance.
				</p>
			</header>

			<main className='app-main'>
				{/* INPUT PANEL */}
				<section className='panel panel--primary'>
					<h2 className='panel__title'>Describe your situation</h2>
					<p className='panel__subtitle'>
						One or two sentences is enough. Avoid sharing personal details like
						full names or exact addresses.
					</p>

					<form className='help-form' onSubmit={handleSubmit}>
						<textarea
							className='help-form__textarea'
							rows={5}
							placeholder='e.g. "I smell gas in my kitchen and I am worried."'
							value={situationText}
							onChange={(e) => setSituationText(e.target.value)}
						/>

						{/* Emergency Guides toggle */}
						<div className='help-form__mode'>
							<label className='mode-toggle'>
								<input
									type='checkbox'
									checked={mode === 'deep'}
									onChange={(e) =>
										setMode(e.target.checked ? 'deep' : 'normal')
									}
									disabled={loading}
								/>
								<span className='mode-toggle__label'>
								    Use Emergency Guides (Google Gemini Files)
								</span>
							</label>
							<p className='mode-toggle__hint'>
								Normal mode is fast and enough for most situations. Use
								Emergency Guides mode uses Google&apos;s Gemini Files API to
								look up relevant emergency-preparedness PDFs (for example,
								flood, wildfire, or earthquake guides) when available, and then
								gives a more detailed answer based on those documents. If
								nothing closely matches, it falls back to general safety advice.
							</p>
						</div>

						{error && <p className='help-form__error'>{error}</p>}

						<div className='help-form__actions'>
							<button className='button button--primary' disabled={loading}>
								{loading ? 'Analyzing...' : 'Get safety steps'}
							</button>
							<button
								type='button'
								className='button button--ghost'
								onClick={handleReset}
								disabled={loading && !result}
							>
								Reset
							</button>
						</div>
					</form>
				</section>

				{/* RESULT PANEL */}
				{result && (
					<section className='panel panel--result'>
						<h2 className='panel__title panel__title--small'>
							Suggested safety steps
						</h2>

						<div className='result-meta'>
							<span className='meta-pill meta-pill--strong'>
								Hazard: <strong>{result.hazard}</strong>
							</span>
							<span className='meta-pill'>
								Source:{' '}
								<strong>
									{result.hazardSource === 'rules' ? 'Rules' : 'AI'}
								</strong>
							</span>
							<span className='meta-pill'>
								Mode: <strong>{resultMode}</strong>
							</span>
							{result.guidesUsed?.length > 0 && mode === 'deep' && (
								<span className='meta-pill meta-pill--soft'>
									Guides: {result.guidesUsed.join(', ')}
								</span>
							)}
						</div>

						<div
							className='guidance'
							dangerouslySetInnerHTML={{
								__html: marked.parse(result.guidance || ''),
							}}
						></div>
					</section>
				)}

				{/* EXAMPLES PANEL */}
				{!result && (
					<section className='panel panel--secondary'>
						<h3 className='panel__title panel__title--small'>
							Try one of these examples
						</h3>
						<ul className='example-list'>
							<li>“My basement is flooding and water is rising quickly.”</li>
							<li>“I smell gas in my kitchen and I am scared.”</li>
							<li>“There is heavy smoke outside from a wildfire.”</li>
							<li>“My car broke down on a busy highway at night.”</li>
						</ul>
					</section>
				)}

				{/* KO-FI SUPPORT PANEL */}
				<section className='panel panel--support'>
					<h3 className='panel__title panel__title--small'>
						Support this project
					</h3>

					<button
						type='button'
						className='button button--kofi button--primary'
						onClick={handleDonateClick}
					>
						Support on Ko-fi
					</button>
					<p className='support-note'>
						Completely optional — your support helps reduce 503 errors, speed up
						slow-thinking AI, and increase happiness by at least 14%.
					</p>
				</section>
			</main>

			<footer className='app-footer'>
				<small>
					This tool only provides general, non-medical safety guidance. For any
					life-threatening situation, call emergency services (911 or your local
					emergency number).
				</small>
			</footer>
		</div>
	);
}

export default App;
