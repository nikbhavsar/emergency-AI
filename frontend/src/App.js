import React, { useEffect, useState } from 'react';
import { trackEvent, trackPageView } from './ga4';
import { marked } from 'marked';

const API_BASE = 'http://127.0.0.1:5000';

function App() {
	const [situationText, setSituationText] = useState('');
	const [mode, setMode] = useState('normal'); // "normal" | "deep"
	const [loading, setLoading] = useState(false);
	const [result, setResult] = useState(null);
	const [error, setError] = useState('');

	useEffect(() => {
		trackPageView('/');
	}, []);

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

		trackEvent({
			action: 'submit_help_request',
			category: 'help',
			label: mode,
		});

		try {
			const res = await fetch(`${API_BASE}${endpoint}`, {
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
			console.error(err);
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

		trackEvent({
			action: 'help_form_reset',
			category: 'help',
			label: 'reset',
		});
	};

	const resultMode = result?.mode || mode;

	return (
		<div className='app'>
			<header className='header'>
				<div className='header-badge'>AI • Safety Assistant</div>
				<h1>Emergency Safety Helper</h1>
				<p className='subtitle'>
					Describe what&apos;s happening and get calm, step-by-step, non-medical
					safety guidance.
				</p>
			</header>

			<main className='center-container'>
				{/* FORM CARD */}
				<section className='card card-main'>
					<h2 className='card-title'>Describe your situation</h2>
					<p className='card-subtitle'>
						One or two sentences is enough. Avoid sharing personal details like
						full names or exact addresses.
					</p>

					<form onSubmit={handleSubmit}>
						<textarea
							className='textarea'
							rows={5}
							placeholder='e.g. "I smell gas in my kitchen and I am worried."'
							value={situationText}
							onChange={(e) => setSituationText(e.target.value)}
						/>

						{/* Deep guidance toggle */}
						<div className='deep-toggle-row'>
							<label className='deep-toggle-label'>
								<input
									type='checkbox'
									checked={mode === 'deep'}
									onChange={(e) =>
										setMode(e.target.checked ? 'deep' : 'normal')
									}
									disabled={loading}
								/>
								<span>Deep guidance (longer, more detailed answer)</span>
							</label>
							<p className='deep-toggle-hint'>
								Normal mode is fast and enough for most situations. Deep mode
								uses enhanced AI processing and can reference uploaded
								emergency-preparedness documents (via the Gemini Files API) to
								generate more context-aware guidance.
							</p>
						</div>

						{error && <p className='error'>{error}</p>}

						<div className='buttons'>
							<button className='btn primary' disabled={loading}>
								{loading ? 'Analyzing...' : 'Get safety steps'}
							</button>
							<button
								type='button'
								className='btn ghost'
								onClick={handleReset}
								disabled={loading && !result}
							>
								Reset
							</button>
						</div>
					</form>
				</section>

				{/* RESULT CARD */}
				{result && (
					<section className='card card-result'>
						<h2 className='card-title'>Suggested safety steps</h2>
						<div className='pill-row'>
							<span className='pill pill-strong'>
								Hazard: <strong>{result.hazard}</strong>
							</span>
							<span className='pill'>
								Source:{' '}
								<strong>
									{result.hazardSource === 'rules' ? 'Rules' : 'AI'}
								</strong>
							</span>
							<span className='pill'>
								Mode: <strong>{resultMode}</strong>
							</span>
							{result.guidesUsed?.length > 0 && (
								<span className='pill pill-soft'>
									Guides: {result.guidesUsed.join(', ')}
								</span>
							)}
						</div>
						<div
							className='guidance-box'
							dangerouslySetInnerHTML={{
								__html: marked.parse(result.guidance),
							}}
						></div>{' '}
					</section>
				)}

				{/* EXAMPLES CARD */}
				{!result && (
					<section className='card card-secondary'>
						<h3 className='card-title'>Try one of these examples</h3>
						<ul className='example-list'>
							<li>“My basement is flooding and water is rising quickly.”</li>
							<li>“I smell gas in my kitchen and I am scared.”</li>
							<li>“There is heavy smoke outside from a wildfire.”</li>
							<li>“My car broke down on a busy highway at night.”</li>
						</ul>
					</section>
				)}
			</main>

			<footer className='footer'>
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
