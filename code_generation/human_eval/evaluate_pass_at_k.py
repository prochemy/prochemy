import argparse


def main(sample_file, problem_file, k_values):
    from evaluate_functional_correctness import entry_point as evaluate
    evaluate(sample_file=sample_file, problem_file=problem_file, k=k_values)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate pass@k value for samples.")
    parser.add_argument('--sample_file', type=str, required=True,
                        help='File containing the samples to evaluate.')
    parser.add_argument('--problem_file', type=str, required=True,
                        help='File containing the problem dataset.')
    parser.add_argument('--k', type=str, default="1,10,100",
                        help='Comma-separated list of k values for pass@k calculation.')

    args = parser.parse_args()

    main(sample_file=args.sample_file, problem_file=args.problem_file, k_values=args.k)